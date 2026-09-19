"""Contrat du client JeV, entierement sans reseau externe."""
import asyncio

from src.ears.jev_reflexe import JevReflexe, JevThresholds, QUESTIONS


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class FakeTransport:
    """Double minimal de httpx.AsyncClient qui garde la liste des POST."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def post(self, url, *, json, headers, timeout):
        self.calls.append({
            "url": url,
            "json": json,
            "headers": headers,
            "timeout": timeout,
        })
        if self.error:
            raise self.error
        return self.response


class SlowTransport(FakeTransport):
    async def post(self, url, *, json, headers, timeout):
        self.calls.append({
            "url": url, "json": json, "headers": headers, "timeout": timeout,
        })
        await asyncio.sleep(0.61)
        return self.response


def _answers(**overrides):
    answers = {
        "addressed_to_mother": {"type": "noul", "noul": 0.91},
        "real_interruption": {"type": "noul", "noul": 0.92},
        "phrase_finished": {"type": "noul", "noul": 0.88},
        "transcription_uncertain": {"type": "noul", "noul": 0.10},
        "expected_response_length": {
            "type": "choice", "choice": "few_sentences", "confidence": 0.81,
            "probabilities": {"one_word": 0.05, "few_sentences": 0.9, "developed": 0.05},
        },
        "tone": {
            "type": "choice", "choice": "empathic", "confidence": 0.82,
            "probabilities": {"calm": 0.1, "cheerful": 0.1, "serious": 0.1, "empathic": 0.7},
        },
        "frustration": {"type": "score", "score": 2.2, "confidence": 0.8},
        "needs_current_information": {"type": "noul", "noul": 0.8},
        "refers_to_context": {"type": "noul", "noul": 0.2},
        "requests_memory": {"type": "noul", "noul": 0.1},
        "sensitive_local_action": {"type": "noul", "noul": 0.1},
        "contains_personal_data": {"type": "noul", "noul": 0.2},
        "named_harness": {
            "type": "choice", "choice": "codex", "confidence": 0.9,
            "probabilities": {"none": 0.05, "claude": 0.05, "codex": 0.9},
        },
    }
    answers.update(overrides)
    return answers


def test_un_seul_post_porte_exactement_les_treize_questions_et_le_bearer():
    transport = FakeTransport(FakeResponse(payload={"answers": _answers()}))
    client = JevReflexe(api_key="cle-de-test", transport=transport)

    result = asyncio.run(client.evaluate("MOTHER, attends une seconde."))

    assert result is not None
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == "https://api.typesafe.ai/v1/systemone"
    assert call["headers"] == {"Authorization": "Bearer cle-de-test", "Content-Type": "application/json"}
    assert call["json"]["model"] == "jev-latest"
    assert tuple(call["json"]["questions"]) == tuple(QUESTIONS)
    assert len(call["json"]["questions"]) == 13
    assert call["json"]["state"]["transcription"] == "MOTHER, attends une seconde."
    assert result.signals.real_interruption is True
    assert result.signals.expected_response_length == "few_sentences"
    assert result.signals.tone == "empathic"
    assert result.signals.frustration == 2.2
    assert result.signals.named_harness == "codex"


def test_absence_de_cle_ne_cree_aucun_client_ni_appel():
    transport = FakeTransport(FakeResponse(payload={"answers": _answers()}))
    client = JevReflexe(api_key="", transport=transport)

    assert asyncio.run(client.evaluate("bonjour")) is None
    assert transport.calls == []


def test_timeout_erreur_http_ou_reponse_incomplete_replient_silencieusement():
    for response, error in (
        (None, TimeoutError("trop lent")),
        (FakeResponse(status_code=503), None),
        (FakeResponse(payload={"answers": {}}), None),
    ):
        client = JevReflexe(api_key="cle-de-test", transport=FakeTransport(response, error))
        assert asyncio.run(client.evaluate("stop")) is None


def test_seuils_sont_injectables_et_ne_declenchent_pas_un_harnais():
    transport = FakeTransport(FakeResponse(payload={"answers": _answers()}))
    client = JevReflexe(
        api_key="cle-de-test",
        transport=transport,
        thresholds=JevThresholds(noul_true=0.95, choice_confidence=0.95, score_confidence=0.95),
    )

    result = asyncio.run(client.evaluate("Codex, fais-le"))

    assert result is not None
    assert result.signals.addressed_to_mother is False
    assert result.signals.expected_response_length is None
    assert result.signals.tone is None
    assert result.signals.frustration is None
    assert result.signals.named_harness is None
    assert not hasattr(result.signals, "send_to_harness")


def test_duree_est_bornee_a_600_ms_meme_si_un_seuil_plus_haut_est_demande():
    transport = FakeTransport(FakeResponse(payload={"answers": _answers()}))
    client = JevReflexe(
        api_key="cle-de-test", transport=transport, thresholds=JevThresholds(timeout_ms=900)
    )

    assert asyncio.run(client.evaluate("bonjour")) is not None
    assert transport.calls[0]["timeout"] == 0.6


def test_budget_mural_de_600_ms_replie_meme_si_le_transport_ignore_son_timeout():
    transport = SlowTransport(FakeResponse(payload={"answers": _answers()}))
    client = JevReflexe(api_key="cle-de-test", transport=transport)

    assert asyncio.run(client.evaluate("bonjour")) is None
