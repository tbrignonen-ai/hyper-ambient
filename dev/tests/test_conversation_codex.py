"""Mode abonnement ChatGPT : une session Codex app-server gardée ouverte.

Mesure du 24/09 : `codex exec` relancé à chaque tour ~4,7 s ; l'app-server
gardé ouvert répond en ~1,4 s, avec la mémoire de la conversation, et
`model/list` donne la liste des modèles en direct.
"""
import json
import queue
import threading

from native.codexbridge.conversation import SessionCodex


class _FauxAppServer:
    """Répond au protocole comme `codex app-server`, ligne JSON par ligne JSON."""

    def __init__(self):
        self.recus = []
        self._sortie = queue.Queue()
        faux = self

        class _Stdin:
            def write(self, texte):
                for ligne in texte.splitlines():
                    if ligne.strip():
                        faux._recevoir(json.loads(ligne))

            def flush(self):
                pass

            def close(self):
                faux._sortie.put(None)

        class _Stdout:
            def __iter__(self):
                while True:
                    ligne = faux._sortie.get()
                    if ligne is None:
                        return
                    yield ligne

        self.stdin = _Stdin()
        self.stdout = _Stdout()

    def poll(self):
        return None

    def terminate(self):
        self._sortie.put(None)

    def _emettre(self, objet):
        self._sortie.put(json.dumps(objet) + "\n")

    def _recevoir(self, message):
        self.recus.append(message)
        methode, ident = message.get("method"), message.get("id")
        if methode == "initialize":
            self._emettre({"id": ident, "result": {}})
        elif methode == "model/list":
            self._emettre({"id": ident, "result": {"data": [
                {"id": "gpt-6-luna", "displayName": "GPT-6-Luna", "hidden": False},
                {"id": "gpt-reserve", "displayName": "GPT-Reserve", "hidden": True},
            ]}})
        elif methode == "thread/start":
            numero = sum(1 for m in self.recus if m.get("method") == "thread/start")
            self._emettre({"id": ident, "result": {"thread": {"id": f"t{numero}"}}})
        elif methode == "turn/start":
            fil = message["params"]["threadId"]
            self._emettre({"id": ident, "result": {"turn": {"id": "u"}}})
            for morceau in ("Lima, ", "au Pérou."):
                self._emettre({"method": "item/agentMessage/delta",
                               "params": {"threadId": fil, "turnId": "u", "itemId": "i", "delta": morceau}})
            self._emettre({"method": "turn/completed", "params": {"threadId": fil, "turn": {"id": "u"}}})


def _session():
    faux = _FauxAppServer()
    session = SessionCodex(modele="gpt-6-luna", effort="low", lancer=lambda *a, **k: faux,
                           prechauffage=False)
    return session, faux


def test_repondre_diffuse_et_fixe_modele_effort_et_consignes():
    session, faux = _session()
    messages = [{"role": "system", "content": "SYS"},
                {"role": "user", "content": "Capitale du Pérou ?"}]
    assert list(session.repondre(messages)) == ["Lima, ", "au Pérou."]
    assert session.derniere_reponse == "Lima, au Pérou."
    fil = next(m for m in faux.recus if m.get("method") == "thread/start")["params"]
    assert fil["model"] == "gpt-6-luna"
    assert fil["developerInstructions"] == "SYS"
    assert fil["sandbox"] == "read-only" and fil["approvalPolicy"] == "never"
    assert fil["config"]["model_reasoning_effort"] == "low"
    tour = next(m for m in faux.recus if m.get("method") == "turn/start")["params"]
    assert tour["effort"] == "low"
    assert tour["input"][0]["text"].endswith("Capitale du Pérou ?")


def test_le_tour_suivant_reste_sur_le_meme_fil():
    session, faux = _session()
    messages = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "Capitale du Pérou ?"}]
    list(session.repondre(messages))
    messages += [{"role": "assistant", "content": "Lima, au Pérou."},
                 {"role": "user", "content": "Et du Chili ?"}]
    list(session.repondre(messages))
    fils = [m for m in faux.recus if m.get("method") == "thread/start"]
    assert len(fils) == 1
    dernier = [m for m in faux.recus if m.get("method") == "turn/start"][-1]["params"]
    assert dernier["input"][0]["text"] == "Et du Chili ?"


def test_models_en_direct_sans_les_caches():
    session, _ = _session()
    assert session.modeles() == [{"id": "gpt-6-luna", "label": "GPT-6-Luna"}]


def test_le_fil_de_conversation_n_a_pas_les_outils_d_action():
    """Séance du 24/09 : « fais apparaître Codex et Claude » — GPT-6-Luna, agent
    muni d'un shell et de computer_use, s'est mis à agir : 25 s sans un mot,
    le host-agent a abandonné. La voix converse ; les harnais agissent."""
    session, faux = _session()
    list(session.repondre([{"role": "system", "content": "SYS"},
                           {"role": "user", "content": "Bonjour"}]))
    config = next(m for m in faux.recus if m.get("method") == "thread/start")["params"]["config"]
    for outil in ("shell_tool", "unified_exec", "computer_use", "browser_use", "apps",
                  "plugins", "multi_agent", "image_generation"):
        assert config[f"features.{outil}"] is False, outil


def test_un_tour_abandonne_ne_deborde_pas_sur_le_suivant():
    """Séance du 24/09 : le host-agent a lâché un tour au bout de 20 s. La fin
    de ce tour restait en file et aurait été lue comme la réponse suivante."""
    session, faux = _session()
    messages = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "Bonjour"}]
    list(session.repondre(messages))
    session._file.put({"method": "item/agentMessage/delta",
                       "params": {"threadId": "t1", "turnId": "vieux", "delta": "reste d'avant "}})
    session._file.put({"method": "turn/completed",
                       "params": {"threadId": "t1", "turn": {"id": "vieux"}}})
    suite = messages + [{"role": "assistant", "content": "Lima, au Pérou."},
                        {"role": "user", "content": "Et ensuite ?"}]
    assert "".join(session.repondre(suite)) == "Lima, au Pérou."
