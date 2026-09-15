"""
Pont hote vers Claude CLI / Hermes CLI : la logique pure, sans lancer de CLI.

Le lanceur de sous-processus est injecte. Ce qui est prouve : la commande Claude
est epinglee en lecture seule, Hermes a une ligne de commande declaree mais n'est
jamais lance si le binaire est absent du PATH, le jeton est exige, et chaque
malheur devient une reponse `{"ok": False}` propre.
"""
import asyncio

from native.clibridge.bridge import (
    MAX_QUESTION_CHARS,
    authorized,
    answer_question,
    build_command,
)


_FLAGS_INTERDITS = (
    "--dangerously-skip-permissions",
    "--allow-dangerously-skip-permissions",
    "bypassPermissions",
    "danger-full-access",
)


def test_la_commande_claude_epingle_le_mode_print_et_la_lecture_seule():
    cmd = build_command("q", agent="claude", workdir="D:/repo")
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "--restricted" in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "plan"
    for flag in _FLAGS_INTERDITS:
        assert flag not in cmd
    assert cmd[-1] == "q"


def test_la_commande_hermes_est_declaree():
    """Le chemin existe sur le papier : argv construit, aucun processus."""
    cmd = build_command("q", agent="hermes")
    assert cmd[0] == "hermes"
    assert "-p" in cmd
    assert cmd[-1] == "q"
    for flag in _FLAGS_INTERDITS:
        assert flag not in cmd


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

    assert _run(answer_question("q", runner=runner)) == {
        "ok": True,
        "answer": "Quatre fichiers.",
    }


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


def test_claude_introuvable_rend_ok_false():
    async def runner(cmd, out_file, timeout_s):
        raise FileNotFoundError("claude")

    r = _run(answer_question("q", runner=runner))
    assert r == {"ok": False, "error": "claude introuvable"}


def test_question_vide_ne_lance_rien():
    appels = []

    async def runner(cmd, out_file, timeout_s):
        appels.append(cmd)
        return 0, "x"

    r = _run(answer_question("   ", runner=runner))
    assert r["ok"] is False and appels == []


def test_hermes_absent_du_path_ne_lance_rien():
    """Hermes reste eteint : pas de binaire, pas de processus, pas d'exception."""
    appels = []

    async def runner(cmd, out_file, timeout_s):
        appels.append(cmd)
        return 0, "x"

    r = _run(
        answer_question(
            "q",
            agent="hermes",
            runner=runner,
            lookup=lambda _name: None,
        )
    )
    assert r == {"ok": False, "error": "hermes indisponible"}
    assert appels == []


def test_hermes_reste_eteint_meme_si_le_binaire_existe():
    """Aujourd'hui on ecrit le chemin, on ne l'emprunte pas — meme installe."""
    appels = []

    async def runner(cmd, out_file, timeout_s):
        appels.append(cmd)
        return 0, "x"

    r = _run(
        answer_question(
            "q",
            agent="hermes",
            runner=runner,
            lookup=lambda _name: r"C:\fake\hermes.exe",
        )
    )
    assert r == {"ok": False, "error": "hermes indisponible"}
    assert appels == []


def test_hermes_n_est_arme_que_par_un_drapeau_explicite(monkeypatch):
    """Le chemin existe : on ne l'ouvre que si CLI_BRIDGE_HERMES=1."""
    monkeypatch.setenv("CLI_BRIDGE_HERMES", "1")
    appels = []

    async def runner(cmd, out_file, timeout_s):
        appels.append(cmd)
        return 0, "ok"

    r = _run(
        answer_question(
            "q",
            agent="hermes",
            runner=runner,
            lookup=lambda _name: r"C:\fake\hermes.exe",
        )
    )
    assert r == {"ok": True, "answer": "ok"}
    assert appels and appels[0][0] == "hermes" and "-p" in appels[0]


def test_agent_inconnu_ne_lance_rien():
    appels = []

    async def runner(cmd, out_file, timeout_s):
        appels.append(cmd)
        return 0, "x"

    r = _run(answer_question("q", agent="muse", runner=runner))
    assert r["ok"] is False and r["error"]
    assert appels == []


def test_la_question_est_bornee_a_2000_caracteres():
    appels = []

    async def runner(cmd, out_file, timeout_s):
        appels.append(cmd[-1])
        return 0, "ok"

    assert MAX_QUESTION_CHARS == 2000
    _run(answer_question("Z" * 5000, runner=runner))
    assert appels[0].count("Z") == MAX_QUESTION_CHARS


def test_l_executable_claude_est_surchargeable():
    cmd = build_command("q", agent="claude", exe=["C:/claude.cmd"])
    assert cmd[0] == "C:/claude.cmd"
    assert "-p" in cmd


def test_aucune_commande_n_a_de_flag_dangereux():
    for agent in ("claude", "hermes"):
        cmd = build_command("q", agent=agent)
        for flag in _FLAGS_INTERDITS:
            assert flag not in cmd
