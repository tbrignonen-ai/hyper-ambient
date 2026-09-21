"""Lot A — sondes d'onboarding, sans reseau.

Le client HTTP est injecte et double a la main. Ce qui est prouve : la forme
des appels (les ponts existants), les trois causes dicibles, le delai borne,
l'absence d'exception, et l'execution parallele de `sonder_tout`.
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import json
import logging
import time

import pytest

from src.brain.tools_cli import CLI_BRIDGE_ENDPOINT
from src.brain.tools_codex import CODEX_BRIDGE_ENDPOINT
from src.ears.jev_reflexe import JEV_ENDPOINT, JEV_MODEL


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class _FakeResponse:
    def __init__(self, payload, status_code=200, content=None):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)
        if content is not None:
            self.content = content
        else:
            self.content = self.text.encode("utf-8")

    def json(self):
        if not isinstance(self._payload, (dict, list)):
            raise ValueError("reponse illisible")
        return self._payload


class FakeHTTPClient:
    """Double du client httpx : rend une reponse scriptee, note les appels."""

    def __init__(self, response=None, raises=None, delay_s=0.0):
        self.response = response if response is not None else _FakeResponse({"ok": True})
        self.raises = raises
        self.delay_s = delay_s
        self.calls = []

    async def post(self, url, json=None, headers=None, timeout=None):
        return await self._appeler("POST", url, json=json, headers=headers, timeout=timeout)

    async def get(self, url, json=None, headers=None, timeout=None):
        return await self._appeler("GET", url, json=json, headers=headers, timeout=timeout)

    async def _appeler(self, methode, url, json=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": methode,
                "url": url,
                "json": json,
                "headers": headers or {},
                "timeout": timeout,
            }
        )
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.raises:
            raise self.raises
        return self.response


def _dicible(detail: str) -> None:
    assert detail.strip()
    assert "{" not in detail
    assert "Traceback" not in detail
    assert "http://" not in detail.lower()
    assert "https://" not in detail.lower()
    assert "HTTP" not in detail
    for code in ("401", "403", "404", "500", "502", "503"):
        assert code not in detail


REGLAGES_OK = {
    "BRAIN_API_ENDPOINT": "http://exemple.invalid/v1/chat/completions",
    "BRAIN_API_KEY": "cle-test",
    "BRAIN_MODEL": "modele-test",
    "CODEX_BRIDGE_URL": "http://exemple.invalid:8765/ask",
    "CODEX_BRIDGE_TOKEN": "jeton-codex",
    "CLI_BRIDGE_URL": "http://exemple.invalid:8766/ask",
    "CLI_BRIDGE_TOKEN": "jeton-claude",
    "TYPESAFE_API_KEY": "cle-jev",
}

# Une reponse qui satisfait les quatre services a la fois : chacun verifie
# autre chose qu'un statut, donc le double doit porter les quatre formes.
PAYLOAD_TOUT_REPOND = {
    "ok": True,
    "reponse": "PONG",
    "question": "…",
    "duree_ms": 1200,
    "choices": [{"message": {"content": "pong"}}],
    "answers": {"phrase_finished": {"noul": 0.9, "confidence": 0.9}},
}


# --- API imposee --------------------------------------------------------


def test_sonde_a_les_champs_imposes():
    from src.onboarding.sondes import Sonde

    champs = {item.name for item in Sonde.__dataclass_fields__.values()}
    assert champs == {"service", "ok", "detail", "latence_ms", "etat"}


def test_sonde_sans_etat_explicite_le_deduit_de_ok():
    """Les appelants existants construisent `Sonde(service, ok, detail, latence)`.

    Un vert sans etat doit rester un vert ; un echec sans etat reste le cas le
    plus prudent, « injoignable », jamais « repond ».
    """
    from src.onboarding.sondes import (
        ETAT_INJOIGNABLE,
        ETAT_REPOND,
        Sonde,
    )

    assert Sonde("codex", True, "oui", 1.0).etat == ETAT_REPOND
    assert Sonde("codex", False, "non", 1.0).etat == ETAT_INJOIGNABLE
    assert Sonde("codex", False, "non", None).etat == ETAT_INJOIGNABLE


def test_les_etats_sont_les_trois_du_brief_plus_l_absent():
    from src.onboarding.sondes import (
        ETAT_ABSENT,
        ETAT_INJOIGNABLE,
        ETAT_MUET,
        ETAT_REPOND,
        ETATS,
    )

    assert ETATS == frozenset(
        {ETAT_REPOND, ETAT_MUET, ETAT_INJOIGNABLE, ETAT_ABSENT}
    )
    assert len({ETAT_REPOND, ETAT_MUET, ETAT_INJOIGNABLE}) == 3


def test_signatures_respectent_l_api_imposee():
    from src.onboarding.sondes import (
        outil_cli_pret,
        sonder_brain_distant,
        sonder_claude,
        sonder_codex,
        sonder_jev,
        sonder_tout,
    )

    assert list(inspect.signature(sonder_brain_distant).parameters) == [
        "endpoint",
        "cle",
        "modele",
        "client",
    ]
    assert list(inspect.signature(sonder_codex).parameters) == ["url", "jeton", "client"]
    assert list(inspect.signature(sonder_claude).parameters) == ["url", "jeton", "client"]
    assert list(inspect.signature(sonder_jev).parameters) == ["cle", "client", "modele"]
    assert inspect.signature(sonder_jev).parameters["modele"].default is None
    assert list(inspect.signature(sonder_tout).parameters) == ["reglages", "client"]
    assert inspect.signature(sonder_codex).parameters["client"].default is None
    assert list(inspect.signature(outil_cli_pret).parameters) == ["nom"]
    assert not inspect.iscoroutinefunction(outil_cli_pret)


def test_le_paquet_reexporte_l_api():
    from src.onboarding import (
        Sonde,
        sonder_brain_distant,
        sonder_claude,
        sonder_codex,
        sonder_jev,
        sonder_tout,
    )

    assert Sonde is not None
    assert callable(sonder_brain_distant)
    assert callable(sonder_codex)
    assert callable(sonder_claude)
    assert callable(sonder_jev)
    assert callable(sonder_tout)


# --- trois causes, quatre services --------------------------------------


@runs_async
async def test_jeton_absent_n_emet_aucun_appel():
    from src.onboarding.sondes import (
        sonder_brain_distant,
        sonder_claude,
        sonder_codex,
        sonder_jev,
    )

    client = FakeHTTPClient()
    sondes = [
        await sonder_brain_distant("http://exemple.invalid/v1", "", "modele", client=client),
        await sonder_codex("http://exemple.invalid/ask", "", client=client),
        await sonder_claude("http://exemple.invalid/ask", "   ", client=client),
        await sonder_jev("", client=client),
    ]

    assert client.calls == []
    assert [sonde.service for sonde in sondes] == [
        "brain_distant",
        "codex",
        "claude",
        "jev",
    ]
    for sonde in sondes:
        assert sonde.ok is False
        assert sonde.latence_ms is None
        _dicible(sonde.detail)
        assert "pas encore" in sonde.detail


@runs_async
async def test_service_injoignable_rend_une_phrase_dicible():
    from src.onboarding.sondes import sonder_codex

    client = FakeHTTPClient(raises=ConnectionRefusedError("connexion refusee"))
    sonde = await sonder_codex("http://exemple.invalid/ask", "jeton", client=client)

    assert sonde.service == "codex"
    assert sonde.ok is False
    _dicible(sonde.detail)
    assert "ne repond pas" in sonde.detail
    assert "ConnectionRefusedError" not in sonde.detail


@runs_async
async def test_jeton_refuse_se_distingue_de_l_injoignable():
    from src.onboarding.sondes import sonder_claude, sonder_codex

    refuse = FakeHTTPClient(_FakeResponse({"ok": False}, status_code=401))
    coupe = FakeHTTPClient(raises=OSError("hote injoignable"))

    refuse_codex = await sonder_codex("http://exemple.invalid/ask", "jeton", client=refuse)
    coupe_codex = await sonder_codex("http://exemple.invalid/ask", "jeton", client=coupe)
    refuse_claude = await sonder_claude("http://exemple.invalid/ask", "jeton", client=refuse)

    assert refuse_codex.ok is False and coupe_codex.ok is False
    assert refuse_codex.detail != coupe_codex.detail
    assert "refuse" in refuse_codex.detail
    assert "ne repond pas" in coupe_codex.detail
    assert "refuse" in refuse_claude.detail
    _dicible(refuse_codex.detail)
    _dicible(coupe_codex.detail)
    _dicible(refuse_claude.detail)


@runs_async
async def test_403_est_un_refus_de_jeton():
    from src.onboarding.sondes import sonder_brain_distant, sonder_jev

    client = FakeHTTPClient(_FakeResponse({"error": "no"}, status_code=403))
    brain = await sonder_brain_distant(
        "http://exemple.invalid/v1/chat/completions",
        "cle-test",
        "modele-test",
        client=client,
    )
    jev = await sonder_jev("cle-test", client=client)

    assert brain.ok is False and jev.ok is False
    assert "refuse" in brain.detail
    assert "refuse" in jev.detail
    _dicible(brain.detail)
    _dicible(jev.detail)


@runs_async
async def test_reponse_ok_pose_la_latence_et_le_service():
    from src.onboarding.sondes import (
        sonder_brain_distant,
        sonder_claude,
        sonder_codex,
        sonder_jev,
    )

    client = FakeHTTPClient(_FakeResponse(PAYLOAD_TOUT_REPOND))
    brain = await sonder_brain_distant(
        "http://exemple.invalid/v1/chat/completions",
        "cle-test",
        "modele-test",
        client=client,
    )
    codex = await sonder_codex("http://exemple.invalid/ask", "jeton", client=client)
    claude = await sonder_claude("http://exemple.invalid/ask", "jeton", client=client)
    jev = await sonder_jev("cle-test", client=client)

    for sonde, nom in (
        (brain, "brain_distant"),
        (codex, "codex"),
        (claude, "claude"),
        (jev, "jev"),
    ):
        assert sonde.service == nom
        assert sonde.ok is True
        assert sonde.latence_ms is not None
        assert sonde.latence_ms >= 0
        _dicible(sonde.detail)
        assert "repondu" in sonde.detail or "repond" in sonde.detail


# --- formes d'appel : ne pas reinventer les ponts -----------------------


@runs_async
async def test_codex_poste_la_question_avec_le_jeton():
    from src.onboarding.sondes import sonder_codex

    client = FakeHTTPClient(_FakeResponse(PAYLOAD_TOUT_REPOND))
    await sonder_codex("http://exemple.invalid:8765/ask", "jeton-codex", client=client)

    assert client.calls, "aucun appel : la sonde n'a rien prouve"
    for envoi in client.calls:
        assert envoi["url"] == "http://exemple.invalid:8765/ask"
        assert envoi["method"] == "POST"
        assert "question" in envoi["json"]
        assert envoi["headers"]["Authorization"] == "Bearer jeton-codex"
    # Le dernier appel est la vraie question, pas la question vide.
    assert client.calls[-1]["json"]["question"].strip()


@runs_async
async def test_claude_poste_l_agent_sur_le_pont_cli():
    from src.onboarding.sondes import sonder_claude

    client = FakeHTTPClient(_FakeResponse(PAYLOAD_TOUT_REPOND))
    await sonder_claude("http://exemple.invalid:8766/ask", "jeton-claude", client=client)

    for envoi in client.calls:
        assert envoi["url"] == "http://exemple.invalid:8766/ask"
        assert envoi["json"]["agent"] == "claude"
        assert "question" in envoi["json"]
        assert envoi["headers"]["Authorization"] == "Bearer jeton-claude"
    assert client.calls[-1]["json"]["question"].strip()


@runs_async
async def test_brain_distant_poste_le_modele_sur_l_endpoint():
    from src.onboarding.sondes import sonder_brain_distant

    client = FakeHTTPClient(_FakeResponse({"choices": [{"message": {"content": "ok"}}]}))
    await sonder_brain_distant(
        "http://exemple.invalid/v1/chat/completions",
        "cle-test",
        "modele-test",
        client=client,
    )

    envoi = client.calls[0]
    assert envoi["url"] == "http://exemple.invalid/v1/chat/completions"
    assert envoi["json"]["model"] == "modele-test"
    assert envoi["headers"]["Authorization"] == "Bearer cle-test"
    assert envoi["timeout"] <= 5


@runs_async
async def test_jev_poste_sur_l_adresse_deja_connue():
    from src.onboarding.sondes import sonder_jev

    client = FakeHTTPClient(_FakeResponse({"answers": {}}))
    await sonder_jev("cle-jev", client=client)

    envoi = client.calls[0]
    assert envoi["url"] == JEV_ENDPOINT
    assert envoi["json"]["model"] == JEV_MODEL
    assert envoi["headers"]["Authorization"] == "Bearer cle-jev"
    assert envoi["timeout"] <= 5


@runs_async
async def test_jev_utilise_le_nom_de_modele_fourni():
    from src.onboarding.sondes import sonder_jev

    client = FakeHTTPClient(_FakeResponse({"answers": {}}))
    await sonder_jev("cle-jev", client=client, modele="jev-autre")

    assert client.calls[0]["json"]["model"] == "jev-autre"


@runs_async
async def test_jev_lit_typesafe_model_si_modele_absent(monkeypatch):
    from src.onboarding.sondes import sonder_jev

    monkeypatch.setenv("TYPESAFE_MODEL", "jev-env")
    client = FakeHTTPClient(_FakeResponse({"answers": {}}))
    await sonder_jev("cle-jev", client=client)

    assert client.calls[0]["json"]["model"] == "jev-env"


# --- aucune exception, delai borne, rien de secret ----------------------


@runs_async
async def test_aucune_exception_ne_sort_du_module():
    from src.onboarding.sondes import sonder_codex, sonder_tout

    class Cassé:
        async def post(self, *args, **kwargs):
            raise RuntimeError("HTTPStatusError 502 at http://secret.invalid")

    sonde = await sonder_codex("http://secret.invalid/ask", "jeton", client=Cassé())
    assert sonde.ok is False
    _dicible(sonde.detail)

    tout = await sonder_tout(REGLAGES_OK, client=Cassé())
    assert len(tout) == 4
    assert all(item.ok is False for item in tout)
    for item in tout:
        _dicible(item.detail)


@runs_async
async def test_une_sonde_qui_pend_est_bornee_a_cinq_secondes():
    from src.onboarding.sondes import sonder_codex

    class Pendu:
        async def post(self, *args, **kwargs):
            await asyncio.sleep(60)

    debut = time.monotonic()
    sonde = await sonder_codex("http://exemple.invalid/ask", "jeton", client=Pendu())
    duree = time.monotonic() - debut

    assert sonde.ok is False
    assert duree < 6.0
    assert "ne repond pas" in sonde.detail
    _dicible(sonde.detail)


@runs_async
async def test_la_cle_n_apparait_jamais_dans_les_journaux(caplog):
    from src.onboarding.sondes import sonder_codex, sonder_jev

    secret = "super-secret-ne-jamais-logger"
    caplog.set_level(logging.DEBUG)
    client = FakeHTTPClient(_FakeResponse({"ok": True}))

    codex = await sonder_codex("http://exemple.invalid/ask", secret, client=client)
    jev = await sonder_jev(secret, client=client)

    assert secret not in caplog.text
    assert secret not in codex.detail
    assert secret not in jev.detail


# --- sonder_tout --------------------------------------------------------


@runs_async
async def test_sonder_tout_rend_les_quatre_services_dans_l_ordre():
    from src.onboarding.sondes import sonder_tout

    client = FakeHTTPClient(_FakeResponse(PAYLOAD_TOUT_REPOND))
    sondes = await sonder_tout(REGLAGES_OK, client=client)

    assert [sonde.service for sonde in sondes] == [
        "brain_distant",
        "codex",
        "claude",
        "jev",
    ]
    assert all(sonde.ok for sonde in sondes)


@runs_async
async def test_sonder_tout_passe_le_modele_jev():
    from src.onboarding.sondes import sonder_tout

    reglages = dict(REGLAGES_OK)
    reglages["TYPESAFE_MODEL"] = "jev-autre"
    client = FakeHTTPClient(_FakeResponse(PAYLOAD_TOUT_REPOND))
    await sonder_tout(reglages, client=client)

    jev = next(appel for appel in client.calls if appel["url"] == JEV_ENDPOINT)
    assert jev["json"]["model"] == "jev-autre"


@runs_async
async def test_sonder_tout_s_execute_en_parallele():
    """Les quatre services partent ensemble ; seuls les deux harnais se suivent.

    Le pont n'a qu'une place : deux questions reelles lancees en meme temps
    renvoient « une demande est deja en cours » et l'un des deux voyants
    serait orange sans raison.
    """
    from src.onboarding.sondes import sonder_tout

    client = FakeHTTPClient(_FakeResponse(PAYLOAD_TOUT_REPOND), delay_s=0.2)
    debut = time.monotonic()
    sondes = await sonder_tout(REGLAGES_OK, client=client)
    duree = time.monotonic() - debut

    assert len(sondes) == 4
    assert all(sonde.ok for sonde in sondes)
    # 6 appels : une question vide + une vraie question par harnais, un par
    # service distant. Deux harnais serialises coutent 0,4 s, pas 1,2 s.
    assert len(client.calls) == 6
    assert duree < 1.1


@runs_async
async def test_sonder_tout_ne_lance_pas_les_deux_harnais_en_meme_temps():
    from src.onboarding.sondes import sonder_tout

    class _UnePlace:
        """Le pont reel refuse une seconde question simultanee."""

        def __init__(self):
            self.calls = []
            self.en_cours = 0
            self.chevauchements = 0

        async def post(self, url, json=None, headers=None, timeout=None):
            self.calls.append({"url": url, "json": json, "timeout": timeout})
            vraie = bool((json or {}).get("question", "").strip())
            if vraie:
                self.en_cours += 1
                if self.en_cours > 1:
                    self.chevauchements += 1
                await asyncio.sleep(0.05)
                self.en_cours -= 1
            return _FakeResponse(PAYLOAD_TOUT_REPOND)

    client = _UnePlace()
    sondes = await sonder_tout(REGLAGES_OK, client=client)

    assert client.chevauchements == 0, "deux questions reelles en meme temps"
    assert len(sondes) == 4


@runs_async
async def test_sonder_tout_sans_reglages_dit_jeton_absent():
    from src.onboarding.sondes import sonder_tout

    client = FakeHTTPClient()
    sondes = await sonder_tout({}, client=client)

    assert client.calls == []
    assert [sonde.service for sonde in sondes] == [
        "brain_distant",
        "codex",
        "claude",
        "jev",
    ]
    assert all(sonde.ok is False for sonde in sondes)
    assert all("pas encore" in sonde.detail for sonde in sondes)


def test_les_adresses_par_defaut_sont_celles_des_ponts():
    """Garde-fou : si sonder_tout complete une URL manquante, ce sont
    les adresses deja connues, pas une invention."""
    assert CODEX_BRIDGE_ENDPOINT.endswith("/ask")
    assert CLI_BRIDGE_ENDPOINT.endswith("/ask")
    assert JEV_ENDPOINT.startswith("https://")


# --- hote alterne : la question est "le pont repond-il", pas cette URL ---


class _ClientHoteAlterneur:
    """Echoue sur host.docker.internal, repond sur 127.0.0.1 — et l'inverse."""

    def __init__(self, *, coupe="host.docker.internal", statut_ok=200):
        self.coupe = coupe
        self.statut_ok = statut_ok
        self.calls = []

    async def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(
            {"url": url, "json": json, "headers": headers or {}, "timeout": timeout}
        )
        if self.coupe in url:
            raise ConnectionError("hote injoignable depuis ici")
        return _FakeResponse(PAYLOAD_TOUT_REPOND, status_code=self.statut_ok)


@runs_async
async def test_pont_retente_sur_l_hote_alterne_et_trouve_le_pont():
    """Mesure du 2026-09-20 : depuis l'hote, host.docker.internal timeout,
    127.0.0.1 repond. L'ecran tourne sur l'hote ; .env.local garde
    host.docker.internal pour l'assistante dans le conteneur."""
    from src.onboarding.sondes import sonder_codex

    client = _ClientHoteAlterneur(coupe="host.docker.internal", statut_ok=200)
    url = "http://host.docker.internal:8765/ask"
    sonde = await sonder_codex(url, "jeton", client=client)

    vus = [envoi["url"] for envoi in client.calls]
    assert vus[0] == url
    assert vus[1] == "http://127.0.0.1:8765/ask"
    # La vraie question reste sur l'hote qui a repondu : on ne revient pas
    # taper sur celui qui est tombe.
    assert all("host.docker.internal" not in vue for vue in vus[1:])
    assert sonde.ok is True
    assert "repondu" in sonde.detail
    _dicible(sonde.detail)


@runs_async
async def test_pont_retente_de_localhost_vers_docker_internal():
    from src.onboarding.sondes import sonder_claude

    client = _ClientHoteAlterneur(coupe="127.0.0.1", statut_ok=200)
    sonde = await sonder_claude("http://127.0.0.1:8766/ask", "jeton", client=client)

    vus = [envoi["url"] for envoi in client.calls]
    assert vus[0] == "http://127.0.0.1:8766/ask"
    assert vus[1] == "http://host.docker.internal:8766/ask"
    assert all("127.0.0.1" not in vue for vue in vus[1:])
    assert sonde.ok is True
    _dicible(sonde.detail)


@runs_async
async def test_pont_joignable_en_401_n_est_pas_un_faux_negatif():
    """Un 401 depuis l'hote alterne prouve que le pont repond.
    Ce n'est plus « ne repond pas »."""
    from src.onboarding.sondes import ETAT_MUET, sonder_codex

    client = _ClientHoteAlterneur(coupe="host.docker.internal", statut_ok=401)
    sonde = await sonder_codex(
        "http://host.docker.internal:8765/ask", "jeton", client=client
    )

    assert len(client.calls) == 2
    assert client.calls[1]["url"] == "http://127.0.0.1:8765/ask"
    assert sonde.ok is False
    assert sonde.etat == ETAT_MUET
    assert "ne repond pas" not in sonde.detail
    assert "refuse" in sonde.detail
    _dicible(sonde.detail)


@runs_async
async def test_pont_n_alterne_pas_une_adresse_qui_n_est_pas_locale():
    from src.onboarding.sondes import sonder_codex

    client = FakeHTTPClient(raises=ConnectionError("coupe"))
    sonde = await sonder_codex("http://exemple.invalid/ask", "jeton", client=client)

    assert len(client.calls) == 1
    assert sonde.ok is False
    assert "ne repond pas" in sonde.detail


@runs_async
async def test_pont_reussi_du_premier_coup_n_invente_pas_de_second_appel():
    """Deux appels vers la meme adresse : le pont, puis le harnais.
    Aucun appel vers un hote qui n'a pas ete demande."""
    from src.onboarding.sondes import sonder_codex

    client = FakeHTTPClient(_FakeResponse(PAYLOAD_TOUT_REPOND))
    await sonder_codex("http://host.docker.internal:8765/ask", "jeton", client=client)
    assert {envoi["url"] for envoi in client.calls} == {
        "http://host.docker.internal:8765/ask"
    }
    assert "127.0.0.1" not in " ".join(envoi["url"] for envoi in client.calls)


# --- harnais CLI : un executable ET une connexion posee -----------------


@pytest.fixture
def maison_vide(tmp_path, monkeypatch):
    """Une machine ou aucun harnais n'a jamais ete connecte."""
    monkeypatch.setattr("src.onboarding.sondes._maison", lambda: tmp_path)
    return tmp_path


def _poser_identifiants(maison, nom: str) -> None:
    """Ecrit la trace locale que laisse l'outil officiel apres `login`."""
    if nom == "codex":
        dossier = maison / ".codex"
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "auth.json").write_text(
            json.dumps(
                {
                    "auth_mode": "chatgpt",
                    "OPENAI_API_KEY": None,
                    "tokens": {"id_token": "faux-jeton-ne-jamais-afficher"},
                    "last_refresh": "2026-09-20T12:00:00Z",
                }
            ),
            encoding="utf-8",
        )
    else:
        dossier = maison / ".claude"
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / ".credentials.json").write_text(
            json.dumps({"claudeAiOauth": {"accessToken": "faux-jeton-ne-jamais-afficher"}}),
            encoding="utf-8",
        )


def test_outil_cli_pret_absent_dit_qu_il_n_est_pas_installe(monkeypatch, maison_vide):
    from src.onboarding.sondes import outil_cli_pret

    monkeypatch.setattr("src.onboarding.sondes.shutil.which", lambda _nom: None)
    sonde = outil_cli_pret("codex")

    assert sonde.service == "codex"
    assert sonde.ok is False
    assert sonde.latence_ms is not None
    _dicible(sonde.detail)
    assert "pas" in sonde.detail.lower()
    assert "codex" in sonde.detail.lower()


def test_outil_cli_pret_installe_sans_connexion_n_est_pas_vert(monkeypatch, maison_vide):
    """Le defaut vise par le brief : un executable present ne prouve pas
    qu'un abonnement est actif. Vert ici = panne garantie en demonstration."""
    from src.onboarding.sondes import ETAT_MUET, outil_cli_pret

    monkeypatch.setattr(
        "src.onboarding.sondes.shutil.which", lambda nom: f"/usr/bin/{nom}"
    )
    sonde = outil_cli_pret("claude")

    assert sonde.service == "claude"
    assert sonde.ok is False
    assert sonde.etat == ETAT_MUET
    _dicible(sonde.detail)
    texte = sonde.detail.lower().replace("é", "e").replace("è", "e")
    assert "claude" in texte
    assert "installe" in texte
    assert "connexion" in texte or "abonnement" in texte
    assert "login" in texte or "claude" in texte


def test_outil_cli_pret_installe_et_connecte_est_vert(monkeypatch, maison_vide):
    from src.onboarding.sondes import ETAT_REPOND, outil_cli_pret

    monkeypatch.setattr(
        "src.onboarding.sondes.shutil.which", lambda nom: f"/usr/bin/{nom}"
    )
    _poser_identifiants(maison_vide, "codex")
    sonde = outil_cli_pret("codex")

    assert sonde.ok is True
    assert sonde.etat == ETAT_REPOND
    _dicible(sonde.detail)
    texte = sonde.detail.lower().replace("é", "e").replace("è", "e")
    assert "codex" in texte
    assert "connexion" in texte or "connecte" in texte


def test_outil_cli_pret_dit_ce_qu_il_prouve_et_ce_qu_il_ne_prouve_pas(
    monkeypatch, maison_vide
):
    """Une connexion posee sur cette machine n'est pas un abonnement actif :
    le libelle ne doit pas promettre plus que la verification reelle."""
    from src.onboarding.sondes import outil_cli_pret

    monkeypatch.setattr(
        "src.onboarding.sondes.shutil.which", lambda nom: f"/usr/bin/{nom}"
    )
    _poser_identifiants(maison_vide, "claude")
    sonde = outil_cli_pret("claude")

    texte = sonde.detail.lower().replace("é", "e").replace("è", "e")
    assert sonde.ok is True
    assert "abonnement" in texte
    # ni jurer que l'abonnement est actif, ni pretendre l'avoir teste
    assert "est actif" not in texte


def test_outil_cli_pret_ne_revele_jamais_le_contenu_des_identifiants(
    monkeypatch, maison_vide, caplog
):
    from src.onboarding.sondes import outil_cli_pret

    monkeypatch.setattr(
        "src.onboarding.sondes.shutil.which", lambda nom: f"/usr/bin/{nom}"
    )
    _poser_identifiants(maison_vide, "codex")
    caplog.set_level(logging.DEBUG)
    sonde = outil_cli_pret("codex")

    assert "faux-jeton-ne-jamais-afficher" not in sonde.detail
    assert "faux-jeton-ne-jamais-afficher" not in caplog.text
    assert "id_token" not in sonde.detail


def test_outil_cli_pret_identifiants_illisible_ne_ment_pas(monkeypatch, maison_vide):
    from src.onboarding.sondes import outil_cli_pret

    monkeypatch.setattr(
        "src.onboarding.sondes.shutil.which", lambda nom: f"/usr/bin/{nom}"
    )
    dossier = maison_vide / ".codex"
    dossier.mkdir(parents=True)
    (dossier / "auth.json").write_text("{ pas du json", encoding="utf-8")
    sonde = outil_cli_pret("codex")

    assert sonde.ok is False
    _dicible(sonde.detail)


def test_outil_cli_pret_aucune_exception_ne_sort(monkeypatch, maison_vide):
    from src.onboarding.sondes import outil_cli_pret

    def boom(_nom):
        raise RuntimeError("which a explose")

    monkeypatch.setattr("src.onboarding.sondes.shutil.which", boom)
    sonde = outil_cli_pret("codex")
    assert sonde.ok is False
    _dicible(sonde.detail)


def test_outil_cli_pret_nom_inconnu_reste_calme(maison_vide):
    from src.onboarding.sondes import outil_cli_pret

    sonde = outil_cli_pret("muse")
    assert sonde.ok is False
    assert sonde.service == "muse"
    _dicible(sonde.detail)


def test_outil_cli_pret_absent_donne_la_commande_powershell(monkeypatch, maison_vide):
    from src.onboarding.sondes import outil_cli_pret

    monkeypatch.setattr("src.onboarding.sondes.shutil.which", lambda _nom: None)
    sonde = outil_cli_pret("codex")

    assert sonde.ok is False
    _dicible(sonde.detail)
    texte = sonde.detail.lower()
    assert "powershell" in texte
    assert "npm install" in texte
    assert "codex" in texte
    assert "est connecte" not in texte.replace("é", "e")


def test_outil_cli_pret_present_sans_connexion_donne_la_commande_de_connexion(
    monkeypatch, maison_vide
):
    from src.onboarding.sondes import outil_cli_pret

    monkeypatch.setattr(
        "src.onboarding.sondes.shutil.which", lambda nom: f"/usr/bin/{nom}"
    )
    sonde = outil_cli_pret("claude")

    assert sonde.ok is False
    _dicible(sonde.detail)
    texte = sonde.detail.lower()
    assert "powershell" in texte
    assert "claude" in texte
    assert "est connecte" not in texte.replace("é", "e")


def test_detecter_abonnements_appelle_les_deux_outils(monkeypatch, maison_vide):
    from src.onboarding.sondes import detecter_abonnements

    vus: list[str] = []

    def faux(nom):
        from src.onboarding.sondes import Sonde

        vus.append(nom)
        return Sonde(nom, nom == "codex", nom, 1.0)

    monkeypatch.setattr("src.onboarding.sondes.outil_cli_pret", faux)
    sondes = detecter_abonnements()
    assert vus == ["codex", "claude"]
    assert [sonde.service for sonde in sondes] == ["codex", "claude"]
    assert sondes[0].ok is True
    assert sondes[1].ok is False


# --- trois etats honnetes, vraie question ------------------------------


@runs_async
async def test_un_pont_qui_repond_ok_false_n_est_plus_un_vert():
    """Le defaut mesure : 200 + `{"ok": false}` en 13 ms etait compte comme
    « Codex repond ». Le pont rend toujours le statut 200 quand le harnais
    n'a rien dit : seul le corps prouve quelque chose."""
    from src.onboarding.sondes import ETAT_MUET, sonder_claude, sonder_codex

    client = FakeHTTPClient(
        _FakeResponse({"ok": False, "error": "question vide"}, status_code=200)
    )
    codex = await sonder_codex("http://exemple.invalid/ask", "jeton", client=client)
    claude = await sonder_claude("http://exemple.invalid/ask", "jeton", client=client)

    for sonde in (codex, claude):
        assert sonde.ok is False
        assert sonde.etat == ETAT_MUET
        _dicible(sonde.detail)
        assert "repondu" not in sonde.detail


@runs_async
async def test_une_reponse_sans_le_mot_attendu_n_est_pas_un_vert():
    from src.onboarding.sondes import ETAT_MUET, sonder_codex

    client = FakeHTTPClient(_FakeResponse({"ok": True, "reponse": ""}))
    sonde = await sonder_codex("http://exemple.invalid/ask", "jeton", client=client)

    assert sonde.ok is False
    assert sonde.etat == ETAT_MUET
    _dicible(sonde.detail)

    bavard = FakeHTTPClient(
        _FakeResponse({"ok": True, "reponse": "Je ne sais pas quoi dire."})
    )
    sonde = await sonder_codex("http://exemple.invalid/ask", "jeton", client=bavard)
    assert sonde.ok is False
    _dicible(sonde.detail)


@runs_async
async def test_la_reponse_attendue_ne_depend_pas_de_la_casse():
    from src.onboarding.sondes import sonder_codex

    for reponse in ("PONG", "pong", "Pong.", "Le mot demande est PONG."):
        client = FakeHTTPClient(_FakeResponse({"ok": True, "reponse": reponse}))
        sonde = await sonder_codex(
            "http://exemple.invalid/ask", "jeton", client=client
        )
        assert sonde.ok is True, reponse
        _dicible(sonde.detail)


@runs_async
async def test_la_question_de_sonde_est_minimale_et_verifiable():
    """La question posee doit etre courte, et sa reponse attendue connue."""
    from src.onboarding.sondes import MARQUEUR_SONDE, QUESTION_SONDE, sonder_codex

    assert QUESTION_SONDE.strip()
    assert len(QUESTION_SONDE) < 200
    assert MARQUEUR_SONDE.lower() in QUESTION_SONDE.lower()

    client = FakeHTTPClient(_FakeResponse(PAYLOAD_TOUT_REPOND))
    await sonder_codex("http://exemple.invalid/ask", "jeton", client=client)
    questions = [envoi["json"]["question"] for envoi in client.calls]
    assert questions[-1] == QUESTION_SONDE


@runs_async
async def test_la_vraie_question_a_un_delai_borne_superieur_a_cinq_secondes():
    """Un harnais met plus de cinq secondes : borner a cinq produirait un
    faux negatif systematique. La borne est annoncee, pas devinee."""
    from src.onboarding.sondes import (
        DELAI_HARNAIS_S,
        DELAI_HARNAIS_SERVEUR_S,
        DELAI_S,
        sonder_codex,
    )

    assert DELAI_S == 5.0
    assert DELAI_HARNAIS_S > DELAI_S
    # Le serveur doit rendre son propre depassement avant que le client
    # abandonne : sinon on dit « injoignable » pour un pont qui repond.
    assert DELAI_HARNAIS_SERVEUR_S < DELAI_HARNAIS_S

    client = FakeHTTPClient(_FakeResponse(PAYLOAD_TOUT_REPOND))
    await sonder_codex("http://exemple.invalid/ask", "jeton", client=client)
    delais = [envoi["timeout"] for envoi in client.calls]
    assert delais[0] <= DELAI_S, "le premier appel doit echouer vite"
    assert delais[-1] <= DELAI_HARNAIS_S
    assert client.calls[-1]["json"]["timeout"] <= DELAI_HARNAIS_SERVEUR_S


@runs_async
async def test_un_harnais_qui_pend_ne_bloque_pas_plus_que_la_borne(monkeypatch):
    """La borne est annoncee et tenue. Ramenee ici a 0,4 s pour que le test
    ne dure pas quatre-vingt-dix secondes."""
    from src.onboarding.sondes import ETAT_MUET, sonder_codex

    monkeypatch.setattr("src.onboarding.sondes.DELAI_HARNAIS_S", 0.4)

    class _PondApresLePont:
        """Le pont repond, le harnais ne rend jamais la main."""

        def __init__(self):
            self.calls = []

        async def post(self, url, json=None, headers=None, timeout=None):
            self.calls.append(json or {})
            if (json or {}).get("question", "").strip():
                await asyncio.sleep(600)
            return _FakeResponse({"ok": False, "error": "question vide"})

    client = _PondApresLePont()
    debut = time.monotonic()
    sonde = await sonder_codex("http://exemple.invalid/ask", "jeton", client=client)
    duree = time.monotonic() - debut

    assert sonde.ok is False
    assert sonde.etat == ETAT_MUET
    assert duree < 2.0
    assert "delai" in sonde.detail.lower().replace("é", "e")
    _dicible(sonde.detail)


@runs_async
async def test_le_pont_occupe_le_dit():
    from src.onboarding.sondes import ETAT_MUET, sonder_codex

    class _Occupe:
        async def post(self, url, json=None, headers=None, timeout=None):
            if (json or {}).get("question", "").strip():
                return _FakeResponse(
                    {"ok": False, "error": "Une demande est déjà en cours"},
                    status_code=429,
                )
            return _FakeResponse({"ok": False, "error": "question vide"})

    sonde = await sonder_codex("http://exemple.invalid/ask", "jeton", client=_Occupe())

    assert sonde.ok is False
    assert sonde.etat == ETAT_MUET
    assert "occupe" in sonde.detail.lower().replace("é", "e")
    _dicible(sonde.detail)


@runs_async
async def test_le_delai_du_serveur_est_dit_comme_un_delai():
    from src.onboarding.sondes import ETAT_MUET, sonder_codex

    class _TropLong:
        async def post(self, url, json=None, headers=None, timeout=None):
            if (json or {}).get("question", "").strip():
                return _FakeResponse(
                    {"ok": False, "error": "délai dépassé"}, status_code=408
                )
            return _FakeResponse({"ok": False, "error": "question vide"})

    sonde = await sonder_codex("http://exemple.invalid/ask", "jeton", client=_TropLong())

    assert sonde.ok is False
    assert sonde.etat == ETAT_MUET
    assert "delai" in sonde.detail.lower().replace("é", "e")
    _dicible(sonde.detail)


@runs_async
async def test_un_harnais_non_connecte_le_dit():
    from src.onboarding.sondes import ETAT_MUET, sonder_codex

    class _PasConnecte:
        async def post(self, url, json=None, headers=None, timeout=None):
            if (json or {}).get("question", "").strip():
                return _FakeResponse(
                    {
                        "ok": False,
                        "error": "codex failed (exit 1)",
                        "erreur": "Error: not logged in",
                        "sortie": "codex: authentication required",
                    }
                )
            return _FakeResponse({"ok": False, "error": "question vide"})

    sonde = await sonder_codex(
        "http://exemple.invalid/ask", "jeton", client=_PasConnecte()
    )

    assert sonde.ok is False
    assert sonde.etat == ETAT_MUET
    texte = sonde.detail.lower().replace("é", "e").replace("è", "e")
    assert "connect" in texte or "login" in texte
    _dicible(sonde.detail)


@runs_async
async def test_injoignable_et_muet_sont_deux_etats_differents():
    from src.onboarding.sondes import (
        ETAT_INJOIGNABLE,
        ETAT_MUET,
        ETAT_REPOND,
        sonder_codex,
    )

    coupe = FakeHTTPClient(raises=ConnectionRefusedError("refuse"))
    muet = FakeHTTPClient(_FakeResponse({"ok": False, "error": "question vide"}))
    pret = FakeHTTPClient(_FakeResponse(PAYLOAD_TOUT_REPOND))

    injoignable = await sonder_codex("http://exemple.invalid/ask", "j", client=coupe)
    silencieux = await sonder_codex("http://exemple.invalid/ask", "j", client=muet)
    vivant = await sonder_codex("http://exemple.invalid/ask", "j", client=pret)

    assert injoignable.etat == ETAT_INJOIGNABLE
    assert silencieux.etat == ETAT_MUET
    assert vivant.etat == ETAT_REPOND
    details = {injoignable.detail, silencieux.detail, vivant.detail}
    assert len(details) == 3, "trois etats doivent donner trois phrases"
    for sonde in (injoignable, silencieux, vivant):
        _dicible(sonde.detail)


@runs_async
async def test_le_jeton_absent_est_un_etat_a_part():
    from src.onboarding.sondes import ETAT_ABSENT, sonder_codex, sonder_jev

    for sonde in (
        await sonder_codex("http://exemple.invalid/ask", "", client=FakeHTTPClient()),
        await sonder_jev("", client=FakeHTTPClient()),
    ):
        assert sonde.ok is False
        assert sonde.etat == ETAT_ABSENT
        assert "pas encore" in sonde.detail
        assert sonde.latence_ms is None


@runs_async
async def test_brain_distant_exige_un_contenu_pas_seulement_un_statut():
    from src.onboarding.sondes import ETAT_MUET, ETAT_REPOND, sonder_brain_distant

    url = "http://exemple.invalid/v1/chat/completions"
    vide = FakeHTTPClient(_FakeResponse({"ok": True, "id": "chatcmpl-1"}))
    sonde = await sonder_brain_distant(url, "cle", "modele", client=vide)
    assert sonde.ok is False
    assert sonde.etat == ETAT_MUET
    _dicible(sonde.detail)

    plein = FakeHTTPClient(
        _FakeResponse({"choices": [{"message": {"content": "pong"}}]})
    )
    sonde = await sonder_brain_distant(url, "cle", "modele", client=plein)
    assert sonde.ok is True
    assert sonde.etat == ETAT_REPOND
    _dicible(sonde.detail)

    vide_de_contenu = FakeHTTPClient(
        _FakeResponse({"choices": [{"message": {"content": "   "}}]})
    )
    sonde = await sonder_brain_distant(url, "cle", "modele", client=vide_de_contenu)
    assert sonde.ok is False
    assert sonde.etat == ETAT_MUET


@runs_async
async def test_jev_exige_la_reponse_a_la_question_posee():
    """La sonde ne pose que `phrase_finished` : une reponse qui ne contient
    pas ce signal ne prouve rien, meme avec un statut de succes."""
    from src.onboarding.sondes import ETAT_MUET, ETAT_REPOND, sonder_jev

    vide = FakeHTTPClient(_FakeResponse({"answers": {}}))
    sonde = await sonder_jev("cle", client=vide)
    assert sonde.ok is False
    assert sonde.etat == ETAT_MUET
    _dicible(sonde.detail)

    autre = FakeHTTPClient(_FakeResponse({"answers": {"real_interruption": {"noul": 0.1}}}))
    sonde = await sonder_jev("cle", client=autre)
    assert sonde.ok is False

    plein = FakeHTTPClient(
        _FakeResponse({"answers": {"phrase_finished": {"noul": 0.9}}})
    )
    sonde = await sonder_jev("cle", client=plein)
    assert sonde.ok is True
    assert sonde.etat == ETAT_REPOND
    _dicible(sonde.detail)


@runs_async
async def test_aucun_service_ne_rend_vert_sur_un_corps_illisible():
    from src.onboarding.sondes import (
        sonder_brain_distant,
        sonder_claude,
        sonder_codex,
        sonder_jev,
    )

    client = FakeHTTPClient(_FakeResponse("du html", status_code=200))
    for sonde in (
        await sonder_codex("http://exemple.invalid/ask", "j", client=client),
        await sonder_claude("http://exemple.invalid/ask", "j", client=client),
        await sonder_jev("j", client=client),
        await sonder_brain_distant("http://exemple.invalid/v1", "j", "m", client=client),
    ):
        assert sonde.ok is False
        _dicible(sonde.detail)


# --- voix TTS (Magpie GET /v1/models) ----------------------------------


MAGPIE_MODELS = {
    "data": [
        {
            "id": "magpietts",
            "capability": "speech",
            "device": "cuda",
            "voices": ["John", "Sofia", "Aria", "Jason", "Leo"],
            "languages": [
                "en-US",
                "es-ES",
                "de-DE",
                "fr-FR",
                "it-IT",
                "vi-VN",
                "hi-IN",
            ],
        }
    ]
}


def test_extraire_voix_modele_lit_data_voices():
    from src.onboarding.sondes import extraire_voix_modele

    assert extraire_voix_modele(MAGPIE_MODELS) == (
        "John",
        "Sofia",
        "Aria",
        "Jason",
        "Leo",
    )


def test_extraire_voix_modele_suit_un_modele_nouveau():
    from src.onboarding.sondes import extraire_voix_modele

    payload = {"data": [{"id": "autre", "voices": ["Nova", "Kai", "Nova"]}]}
    assert extraire_voix_modele(payload) == ("Nova", "Kai")


def test_extraire_voix_modele_repli_sur_forme_inconnue():
    from src.onboarding.sondes import extraire_voix_modele

    assert extraire_voix_modele(None) == ()
    assert extraire_voix_modele({"data": []}) == ()
    assert extraire_voix_modele({"voices": ["John"]}) == ()
    assert extraire_voix_modele("pas-json") == ()


def test_extraire_langues_modele_lit_data_languages():
    from src.onboarding.sondes import extraire_langues_modele

    assert extraire_langues_modele(MAGPIE_MODELS) == (
        "en-US",
        "es-ES",
        "de-DE",
        "fr-FR",
        "it-IT",
        "vi-VN",
        "hi-IN",
    )


def test_extraire_langues_modele_suit_un_modele_nouveau():
    from src.onboarding.sondes import extraire_langues_modele

    payload = {"data": [{"id": "autre", "languages": ["pt-BR", "ja-JP", "pt-BR"]}]}
    assert extraire_langues_modele(payload) == ("pt-BR", "ja-JP")


def test_extraire_langues_modele_repli_sur_forme_inconnue():
    from src.onboarding.sondes import extraire_langues_modele

    assert extraire_langues_modele(None) == ()
    assert extraire_langues_modele({"data": []}) == ()
    assert extraire_langues_modele({"languages": ["en-US"]}) == ()
    assert extraire_langues_modele("pas-json") == ()


@runs_async
async def test_lister_voix_tts_prend_la_liste_du_serveur():
    from src.onboarding.sondes import lister_voix_tts

    client = FakeHTTPClient(response=_FakeResponse(MAGPIE_MODELS))
    resultat = await lister_voix_tts(client=client)
    assert resultat.depuis_serveur is True
    assert resultat.voix == ("John", "Sofia", "Aria", "Jason", "Leo")
    assert resultat.langues == (
        "en-US",
        "es-ES",
        "de-DE",
        "fr-FR",
        "it-IT",
        "vi-VN",
        "hi-IN",
    )
    assert client.calls
    assert client.calls[0]["method"] == "GET"
    assert client.calls[0]["url"].endswith("/v1/models")
    assert "8092" in client.calls[0]["url"]


@runs_async
async def test_lister_voix_tts_se_rabat_si_injoignable():
    from src.onboarding.sondes import LANGUES_TTS_REPLI, VOIX_TTS_REPLI, lister_voix_tts

    client = FakeHTTPClient(raises=TimeoutError("coupe"))
    resultat = await lister_voix_tts(client=client)
    assert resultat.depuis_serveur is False
    assert resultat.voix == VOIX_TTS_REPLI
    assert resultat.langues == LANGUES_TTS_REPLI


@runs_async
async def test_lister_voix_tts_se_rabat_si_reponse_illisible():
    from src.onboarding.sondes import LANGUES_TTS_REPLI, VOIX_TTS_REPLI, lister_voix_tts

    client = FakeHTTPClient(response=_FakeResponse("html", status_code=404))
    resultat = await lister_voix_tts(client=client)
    assert resultat.depuis_serveur is False
    assert resultat.voix == VOIX_TTS_REPLI
    assert resultat.langues == LANGUES_TTS_REPLI


@runs_async
async def test_lister_voix_tts_essaie_l_url_alternee():
    from src.onboarding.sondes import lister_voix_tts

    class _PremierRate:
        def __init__(self):
            self.calls = []

        async def get(self, url, json=None, headers=None, timeout=None):
            self.calls.append(url)
            if "127.0.0.1" in url:
                raise ConnectionError("refuse")
            return _FakeResponse({"data": [{"voices": ["Kai"]}]})

    client = _PremierRate()
    resultat = await lister_voix_tts(client=client)
    assert resultat.depuis_serveur is True
    assert resultat.voix == ("Kai",)
    assert resultat.langues == ()
    assert any("127.0.0.1" in url for url in client.calls)
    assert any("host.docker.internal" in url for url in client.calls)


@runs_async
async def test_synthetiser_extrait_tts_envoie_voix_et_langue():
    from src.onboarding.sondes import synthetiser_extrait_tts

    wav = b"RIFF....WAVE"
    client = FakeHTTPClient(response=_FakeResponse({}, content=wav))
    rendu = await synthetiser_extrait_tts(
        "Aria", "en-US", "Bonjour, je suis là.", client=client
    )
    assert rendu == wav
    assert client.calls
    assert client.calls[0]["method"] == "POST"
    assert client.calls[0]["url"].endswith("/v1/audio/speech")
    assert client.calls[0]["json"]["voice"] == "Aria"
    assert client.calls[0]["json"]["language"] == "en-US"
    assert client.calls[0]["json"]["input"] == "Bonjour, je suis là."


@runs_async
async def test_synthetiser_extrait_tts_se_rabat_si_injoignable():
    from src.onboarding.sondes import synthetiser_extrait_tts

    client = FakeHTTPClient(raises=TimeoutError("coupe"))
    assert await synthetiser_extrait_tts("Sofia", "fr", "bonjour", client=client) == b""
