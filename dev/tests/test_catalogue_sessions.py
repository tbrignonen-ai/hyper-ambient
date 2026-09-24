"""Le catalogue des sessions Claude Code et Codex de l'utilisateur (24/09).

« Reprends la dernière session Claude », « la session qui parle de X ou Y » :
le pont lit les sessions là où les harnais les rangent, sans les modifier —
titre (renommage Claude, nom de fil Codex) et premier message utile.
"""
import json
import os
import time

from native import sessions_harnais as sh


def _jsonl(chemin, lignes, mtime=None):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in lignes) + "\n",
                      encoding="utf-8")
    if mtime is not None:
        os.utime(chemin, (mtime, mtime))


def _claude(racine, ident, *, titre=None, premier="Bonjour", cwd="D:\\repo", mtime=None):
    lignes = [
        {"type": "user", "isMeta": True, "cwd": cwd,
         "message": {"role": "user", "content": "<local-command-caveat>bruit</local-command-caveat>"}},
        {"type": "user", "cwd": cwd, "message": {"role": "user", "content": [
            {"type": "text", "text": premier}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": "ok"}},
    ]
    if titre:
        lignes.append({"type": "custom-title", "customTitle": titre, "sessionId": ident})
    _jsonl(racine / "D--repo" / f"{ident}.jsonl", lignes, mtime)


def _codex(racine, ident, *, premier="Bonjour", cwd="D:\\repo", mtime=None):
    lignes = [
        {"type": "session_meta", "payload": {"id": ident, "cwd": cwd}},
        {"type": "event_msg", "payload": {"type": "item_completed", "item": {
            "type": "UserMessage", "content": [{"type": "text", "text": "<recommended_plugins>x"}]}}},
        {"type": "event_msg", "payload": {"type": "item_completed", "item": {
            "type": "UserMessage", "content": [{"type": "text", "text": premier}]}}},
    ]
    _jsonl(racine / "sessions" / "2026" / "09" / "24" / f"rollout-2026-09-24T10-00-00-{ident}.jsonl",
           lignes, mtime)


def test_claude_titre_premier_message_et_dossier(tmp_path):
    _claude(tmp_path, "c-1", titre="SOUTENANCE-TEST", premier="Prépare la démo n8n")
    (s,) = sh.sessions_claude(tmp_path)
    assert s["id"] == "c-1"
    assert s["titre"] == "SOUTENANCE-TEST"
    assert s["apercu"] == "Prépare la démo n8n"
    assert s["cwd"] == "D:\\repo"
    assert s["harnais"] == "Claude"


def test_la_consigne_vocale_du_pont_est_retiree_de_l_apercu(tmp_path):
    _claude(tmp_path, "c-1", premier=(
        "Reponds en francais, en deux ou trois phrases parlables, sans code, "
        "sans liste ni markdown. Question : Lis le README"))
    assert sh.sessions_claude(tmp_path)[0]["apercu"] == "Lis le README"


def test_codex_nom_de_fil_depuis_l_index(tmp_path):
    _codex(tmp_path, "x-1", premier="Regarde le log")
    (tmp_path / "session_index.jsonl").write_text(
        json.dumps({"id": "x-1", "thread_name": "Regarde le log demandé"}) + "\n", encoding="utf-8")
    (s,) = sh.sessions_codex(tmp_path)
    assert (s["id"], s["titre"], s["apercu"], s["cwd"], s["harnais"]) == (
        "x-1", "Regarde le log demandé", "Regarde le log", "D:\\repo", "Codex")


def test_sans_requete_la_plus_recente(tmp_path):
    maintenant = time.time()
    _claude(tmp_path, "vieille", mtime=maintenant - 100)
    _claude(tmp_path, "recente", mtime=maintenant)
    assert sh.chercher(sh.sessions_claude(tmp_path), "")["id"] == "recente"


def test_x_ou_y_dans_le_titre_sans_accents_ni_casse(tmp_path):
    maintenant = time.time()
    _claude(tmp_path, "a", titre="Démo N8N", mtime=maintenant - 50)
    _claude(tmp_path, "b", titre="Voix Magpie", mtime=maintenant)
    _claude(tmp_path, "c", premier="on parle de la demo", mtime=maintenant - 10)
    trouve = sh.chercher(sh.sessions_claude(tmp_path), "demo ou soutenance")
    # Le titre pèse plus que le premier message.
    assert trouve["id"] == "a"
    assert trouve["score"] > 0


def test_rien_ne_correspond(tmp_path):
    _claude(tmp_path, "a", titre="Voix")
    assert sh.chercher(sh.sessions_claude(tmp_path), "facturation") is None


def test_le_dossier_d_une_session_se_retrouve_par_son_identifiant(tmp_path):
    _claude(tmp_path, "c-9", cwd="D:\\autre")
    _codex(tmp_path / "cx", "x-9", cwd="D:\\ailleurs")
    assert sh.cwd_de_session("Claude", "c-9", racine=tmp_path) == "D:\\autre"
    assert sh.cwd_de_session("Codex", "x-9", racine=tmp_path / "cx") == "D:\\ailleurs"
    assert sh.cwd_de_session("Claude", "inconnue", racine=tmp_path) is None


def test_l_apercu_est_parlable(tmp_path):
    _claude(tmp_path, "c-1", premier="# SEED CODEX — Soutenance\n\nTu es   lead")
    assert sh.sessions_claude(tmp_path)[0]["apercu"] == "SEED CODEX — Soutenance Tu es lead"
