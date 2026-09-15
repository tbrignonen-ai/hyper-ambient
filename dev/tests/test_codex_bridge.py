"""
Pont hote vers Codex : la logique pure, sans lancer Codex.

Le lanceur de sous-processus est injecte. Ce qui est prouve : la commande est
epinglee en lecture seule, le jeton est exige, et chaque malheur (Codex absent,
trop lent, code de sortie non nul) devient une reponse `{"ok": False}` propre.
"""
import asyncio

from native.codexbridge.bridge import build_command, authorized, answer_question


def test_la_commande_epingle_le_bac_a_sable_lecture_seule():
    cmd = build_command("q", workdir="D:/repo", out_file="out.txt")
    assert cmd[1] == "exec"
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert "danger-full-access" not in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
    assert cmd[cmd.index("-C") + 1] == "D:/repo"
    assert cmd[cmd.index("-o") + 1] == "out.txt"
    assert cmd[-1] == "q"


def test_le_jeton_est_exige():
    assert authorized("Bearer s3cret", "s3cret")
    assert not authorized("Bearer autre", "s3cret")
    assert not authorized("", "s3cret")
    assert not authorized("Bearer ", "")  # pont sans jeton configure : ferme


def _run(coro):
    return asyncio.run(coro)


def test_reponse_ok_rend_le_dernier_message():
    async def runner(cmd, out_file, timeout_s):
        return 0, "Quatre fichiers."
    assert _run(answer_question("q", runner=runner)) == {"ok": True, "answer": "Quatre fichiers."}


def test_code_de_sortie_non_nul_rend_ok_false():
    async def runner(cmd, out_file, timeout_s):
        return 2, ""
    r = _run(answer_question("q", runner=runner))
    assert r["ok"] is False and r["error"]


def test_delai_depasse_rend_ok_false():
    async def runner(cmd, out_file, timeout_s):
        raise asyncio.TimeoutError()
    r = _run(answer_question("q", runner=runner))
    assert r == {"ok": False, "error": "delai depasse"}


def test_codex_introuvable_rend_ok_false():
    async def runner(cmd, out_file, timeout_s):
        raise FileNotFoundError("codex")
    r = _run(answer_question("q", runner=runner))
    assert r == {"ok": False, "error": "codex introuvable"}


def test_question_vide_ne_lance_rien():
    appels = []
    async def runner(cmd, out_file, timeout_s):
        appels.append(cmd)
        return 0, "x"
    r = _run(answer_question("   ", runner=runner))
    assert r["ok"] is False and appels == []


def test_le_modele_et_l_executable_sont_surchargeables():
    """La config Codex de l'hote peut viser un modele que la CLI installee
    refuse : le pont doit pouvoir epingler l'un et l'autre."""
    cmd = build_command("q", out_file="o", exe=["npx", "-y", "@openai/codex@0.154.0"], model="m1")
    assert cmd[:4] == ["npx", "-y", "@openai/codex@0.154.0", "exec"]
    assert cmd[cmd.index("-m") + 1] == "m1"
    assert "-m" not in build_command("q", out_file="o", exe=["codex"])
