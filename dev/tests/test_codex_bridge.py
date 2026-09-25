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


def test_session_verrouillee_par_la_console_presence_est_liberee_puis_reprise():
    """25/09 : la console `codex resume <id>` ouverte par Presence verrouille le
    fil ; le 2e message partait en erreur. Le pont la ferme et réessaie, dans
    la même session."""
    import asyncio as _asyncio

    from native.codexbridge import bridge as b

    appels = []
    liberees = []

    async def runner(cmd, out_file, timeout_s):
        appels.append(cmd)
        if len(appels) == 1:
            return 1, "", "", "Error: thread 01a0 already has an active writer (code -32600)"
        return 0, "Oui, je suis prêt.", ""

    def liberer(session):
        liberees.append(session)
        return True

    reponse = _asyncio.run(b.answer_question(
        "prêt ?", runner=runner, session="01a0", liberer=liberer, pause_s=0))
    assert reponse == {"ok": True, "answer": "Oui, je suis prêt.", "session_id": "01a0"}
    assert liberees == ["01a0"]
    assert all("resume" in c and "01a0" in c for c in appels)


def test_autre_echec_n_est_pas_retente():
    import asyncio as _asyncio

    from native.codexbridge import bridge as b

    async def runner(cmd, out_file, timeout_s):
        return 1, "", "", "Error: quota"

    def liberer(session):
        raise AssertionError("ne doit pas fermer de console")

    reponse = _asyncio.run(b.answer_question(
        "prêt ?", runner=runner, session="01a0", liberer=liberer, pause_s=0))
    assert reponse["ok"] is False


def test_liberer_ne_vise_que_les_consoles_conhost_de_la_session():
    from native.codexbridge import bridge as b

    processus = [
        {"ProcessId": 11, "Name": "conhost.exe",
         "CommandLine": r'conhost.exe C:\npm\codex.cmd resume 01a0'},
        {"ProcessId": 12, "Name": "node.exe",
         "CommandLine": r'node codex.js resume 01a0'},
        {"ProcessId": 13, "Name": "conhost.exe",
         "CommandLine": r'conhost.exe C:\npm\codex.cmd resume 99ff'},
        {"ProcessId": 14, "Name": "WindowsTerminal.exe",
         "CommandLine": r'codex resume 01a0'},
    ]
    assert b.consoles_de_session(processus, "01a0") == [11]
