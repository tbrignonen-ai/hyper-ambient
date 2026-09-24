"""Budget serveur : tokens réels du template, sans poids ni Metal."""
from types import SimpleNamespace

import pytest

from native.macos.text_server import bounded_tokenize


@pytest.mark.parametrize("requested,expected", [(1, 1), (256, 256), (4096, 256)])
def test_budget_inclut_sortie_et_conserve_template(requested, expected):
    result = (list(range(2048 - expected)), [[1]], ["system"], "reasoning")
    args = SimpleNamespace(max_tokens=requested)
    hook = bounded_tokenize(lambda *unused: result)
    assert hook(None, None, None, args) is result
    assert args.max_tokens == expected


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("request_type", ["chat", "text"])
def test_depassement_rejete_apres_template_sans_troncature(stream, request_type):
    request = SimpleNamespace(request_type=request_type, stream=stream,
                              messages=[{"role": "user", "content": "court"}],
                              tools=[{"name": "outil_long"}])
    tokens = list(range(1793))
    def original(self, tokenizer, received, args):
        assert received is request
        return tokens, [tokens], ["user"], "normal"
    with pytest.raises(ValueError, match="1793.*256.*2048"):
        bounded_tokenize(original)(None, None, request, SimpleNamespace(max_tokens=256))
    assert len(tokens) == 1793


@pytest.mark.parametrize("budget", [0, -1, True, 1.5, None])
def test_budget_invalide_refuse_avant_tokenisation(budget):
    def original(*unused):
        pytest.fail("ne doit pas tokeniser")
    with pytest.raises(ValueError, match="entier"):
        bounded_tokenize(original)(None, None, None, SimpleNamespace(max_tokens=budget))


def test_contrat_incompatible_refuse():
    with pytest.raises(RuntimeError, match="incompatible"):
        bounded_tokenize(lambda *unused: ([], []))(None, None, None, SimpleNamespace(max_tokens=1))


def test_environnement_vide_ne_reprend_pas_le_profil_du_processus(monkeypatch):
    from native.macos import profile
    monkeypatch.setenv("MOTHER_PROFILE", profile.NAME)
    target = {}
    assert profile.apply(target) == {}


def test_superviseur_dry_run_signale_configuration_invalide(tmp_path):
    from dev.scripts.supervise_macos import main
    config = tmp_path / "incorrect.env"
    config.write_text("MOTHER_PROFILE=inconnu\n", encoding="utf-8")
    assert main(["--config", str(config), "--dry-run"]) == 1
