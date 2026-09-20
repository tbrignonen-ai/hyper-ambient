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

from src.brain.tools_cli import CLI_BRIDGE_ENDPOINT
from src.brain.tools_codex import CODEX_BRIDGE_ENDPOINT
from src.ears.jev_reflexe import JEV_ENDPOINT, JEV_MODEL


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)

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
        self.calls.append(
            {"url": url, "json": json, "headers": headers or {}, "timeout": timeout}
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


# --- API imposee --------------------------------------------------------


def test_sonde_a_les_champs_imposes():
    from src.onboarding.sondes import Sonde

    champs = {item.name for item in Sonde.__dataclass_fields__.values()}
    assert champs == {"service", "ok", "detail", "latence_ms"}


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

    client = FakeHTTPClient(_FakeResponse({"ok": True, "answer": "oui"}))
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
        assert "repond" in sonde.detail


# --- formes d'appel : ne pas reinventer les ponts -----------------------


@runs_async
async def test_codex_poste_la_question_avec_le_jeton():
    from src.onboarding.sondes import sonder_codex

    client = FakeHTTPClient(_FakeResponse({"ok": True}))
    await sonder_codex("http://exemple.invalid:8765/ask", "jeton-codex", client=client)

    assert len(client.calls) == 1
    envoi = client.calls[0]
    assert envoi["url"] == "http://exemple.invalid:8765/ask"
    assert "question" in envoi["json"]
    assert envoi["headers"]["Authorization"] == "Bearer jeton-codex"
    assert envoi["timeout"] <= 5


@runs_async
async def test_claude_poste_l_agent_sur_le_pont_cli():
    from src.onboarding.sondes import sonder_claude

    client = FakeHTTPClient(_FakeResponse({"ok": True}))
    await sonder_claude("http://exemple.invalid:8766/ask", "jeton-claude", client=client)

    envoi = client.calls[0]
    assert envoi["url"] == "http://exemple.invalid:8766/ask"
    assert envoi["json"]["agent"] == "claude"
    assert "question" in envoi["json"]
    assert envoi["headers"]["Authorization"] == "Bearer jeton-claude"
    assert envoi["timeout"] <= 5


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

    client = FakeHTTPClient(_FakeResponse({"ok": True, "answer": "oui"}))
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
    client = FakeHTTPClient(_FakeResponse({"ok": True, "answer": "oui"}))
    await sonder_tout(reglages, client=client)

    jev = next(appel for appel in client.calls if appel["url"] == JEV_ENDPOINT)
    assert jev["json"]["model"] == "jev-autre"


@runs_async
async def test_sonder_tout_s_execute_en_parallele():
    from src.onboarding.sondes import sonder_tout

    client = FakeHTTPClient(_FakeResponse({"ok": True}), delay_s=0.2)
    debut = time.monotonic()
    sondes = await sonder_tout(REGLAGES_OK, client=client)
    duree = time.monotonic() - debut

    assert len(sondes) == 4
    assert duree < 0.55
    assert len(client.calls) == 4


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
        return _FakeResponse({"ok": True}, status_code=self.statut_ok)


@runs_async
async def test_pont_retente_sur_l_hote_alterne_et_trouve_le_pont():
    """Mesure du 2026-09-20 : depuis l'hote, host.docker.internal timeout,
    127.0.0.1 repond. L'ecran tourne sur l'hote ; .env.local garde
    host.docker.internal pour l'assistante dans le conteneur."""
    from src.onboarding.sondes import sonder_codex

    client = _ClientHoteAlterneur(coupe="host.docker.internal", statut_ok=200)
    url = "http://host.docker.internal:8765/ask"
    sonde = await sonder_codex(url, "jeton", client=client)

    assert [envoi["url"] for envoi in client.calls] == [
        "http://host.docker.internal:8765/ask",
        "http://127.0.0.1:8765/ask",
    ]
    assert sonde.ok is True
    assert "repond" in sonde.detail
    _dicible(sonde.detail)


@runs_async
async def test_pont_retente_de_localhost_vers_docker_internal():
    from src.onboarding.sondes import sonder_claude

    client = _ClientHoteAlterneur(coupe="127.0.0.1", statut_ok=200)
    sonde = await sonder_claude("http://127.0.0.1:8766/ask", "jeton", client=client)

    assert [envoi["url"] for envoi in client.calls] == [
        "http://127.0.0.1:8766/ask",
        "http://host.docker.internal:8766/ask",
    ]
    assert sonde.ok is True
    _dicible(sonde.detail)


@runs_async
async def test_pont_joignable_en_401_n_est_pas_un_faux_negatif():
    """Un 401 depuis l'hote alterne prouve que le pont repond.
    Ce n'est plus « ne repond pas »."""
    from src.onboarding.sondes import sonder_codex

    client = _ClientHoteAlterneur(coupe="host.docker.internal", statut_ok=401)
    sonde = await sonder_codex(
        "http://host.docker.internal:8765/ask", "jeton", client=client
    )

    assert len(client.calls) == 2
    assert client.calls[1]["url"] == "http://127.0.0.1:8765/ask"
    assert sonde.ok is False
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
    from src.onboarding.sondes import sonder_codex

    client = FakeHTTPClient(_FakeResponse({"ok": True}))
    await sonder_codex("http://host.docker.internal:8765/ask", "jeton", client=client)
    assert [envoi["url"] for envoi in client.calls] == [
        "http://host.docker.internal:8765/ask",
    ]


# --- harnais CLI : un executable, pas une cle API -----------------------


def test_outil_cli_pret_absent_dit_qu_il_n_est_pas_installe(monkeypatch):
    from src.onboarding.sondes import outil_cli_pret

    monkeypatch.setattr("src.onboarding.sondes.shutil.which", lambda _nom: None)
    sonde = outil_cli_pret("codex")

    assert sonde.service == "codex"
    assert sonde.ok is False
    assert sonde.latence_ms is not None
    _dicible(sonde.detail)
    assert "pas" in sonde.detail.lower()
    assert "codex" in sonde.detail.lower()


def test_outil_cli_pret_present_ne_pretend_pas_verifier_l_abonnement(monkeypatch):
    from src.onboarding.sondes import outil_cli_pret

    monkeypatch.setattr(
        "src.onboarding.sondes.shutil.which", lambda nom: f"/usr/bin/{nom}"
    )
    sonde = outil_cli_pret("claude")

    assert sonde.service == "claude"
    assert sonde.ok is True
    assert sonde.latence_ms is not None
    _dicible(sonde.detail)
    assert "claude" in sonde.detail.lower()
    texte = sonde.detail.lower()
    assert "install" in texte or "present" in texte
    assert "abonnement" in texte or "connexion" in texte


def test_outil_cli_pret_aucune_exception_ne_sort(monkeypatch):
    from src.onboarding.sondes import outil_cli_pret

    def boom(_nom):
        raise RuntimeError("which a explose")

    monkeypatch.setattr("src.onboarding.sondes.shutil.which", boom)
    sonde = outil_cli_pret("codex")
    assert sonde.ok is False
    _dicible(sonde.detail)


def test_outil_cli_pret_nom_inconnu_reste_calme():
    from src.onboarding.sondes import outil_cli_pret

    sonde = outil_cli_pret("muse")
    assert sonde.ok is False
    assert sonde.service == "muse"
    _dicible(sonde.detail)


def test_outil_cli_pret_absent_donne_la_commande_powershell(monkeypatch):
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


def test_outil_cli_pret_present_donne_la_commande_sans_affirmer_la_connexion(
    monkeypatch,
):
    from src.onboarding.sondes import outil_cli_pret

    monkeypatch.setattr(
        "src.onboarding.sondes.shutil.which", lambda nom: f"/usr/bin/{nom}"
    )
    sonde = outil_cli_pret("claude")

    assert sonde.ok is True
    _dicible(sonde.detail)
    texte = sonde.detail.lower()
    assert "powershell" in texte
    assert "claude" in texte
    assert "verifi" in texte.replace("é", "e")
    assert "est connecte" not in texte.replace("é", "e")


def test_detecter_abonnements_appelle_les_deux_outils(monkeypatch):
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
