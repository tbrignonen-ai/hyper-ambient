"""À l'arrivée d'une réponse de harnais, sa conversation s'affiche dans le harnais.

Séance du 24/09 : « Le détail est dans Claude » ne menait nulle part. Presence
ouvre désormais la session du mandat dans une console (`claude --resume`,
`codex resume`), au premier plan ou réduite selon le choix de l'écran
principal ; la conversation est affichée dans les deux cas.
"""
from native.presence import harnais_ouvert as ho
from native.presence.onboarding import normaliser_configuration


def test_commande_claude_reprend_la_session():
    assert ho.commande("Claude", "s-1", exe=lambda n: f"/bin/{n}", mode_claude=None) == [
        "/bin/claude", "--resume", "s-1"]


def test_la_console_claude_s_ouvre_dans_le_mode_habituel_pas_en_plan():
    """La session du pont est en lecture seule ; la console est celle de
    l'utilisateur : elle reprend son mode par défaut, pas /plan (24/09)."""
    assert ho.commande("Claude", "s-1", exe=lambda n: n, mode_claude="bypassPermissions") == [
        "claude", "--resume", "s-1", "--permission-mode", "bypassPermissions"]


def test_mode_par_defaut_lu_dans_les_reglages_claude(tmp_path):
    import json

    reglages = tmp_path / "settings.json"
    reglages.write_text(json.dumps({"permissions": {"defaultMode": "acceptEdits"}}), encoding="utf-8")
    assert ho.mode_claude_par_defaut(reglages) == "acceptEdits"
    assert ho.mode_claude_par_defaut(tmp_path / "absent.json") == "manual"


def test_commande_codex_reprend_la_session():
    assert ho.commande("Codex", "th-1", exe=lambda n: f"/bin/{n}") == [
        "/bin/codex", "resume", "th-1"]


def test_harnais_inconnu_ou_sans_session_n_ouvre_rien():
    assert ho.commande("Muse", "x") is None
    assert ho.commande("Claude", "") is None


class _Proc:
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None


class _Lanceur:
    def __init__(self):
        self.appels = []
        self.fermes = []

    def lancer(self, cmd, **options):
        self.appels.append((cmd, options))
        return _Proc(len(self.appels))

    def fermer(self, proc):
        self.fermes.append(proc.pid)


def _ouvreur(lanceur):
    return ho.OuvreurHarnais(
        racine="D:/repo", lancer=lanceur.lancer, fermer=lanceur.fermer,
        exe=lambda n: n, mode_claude=None,
    )


def test_ouvre_dans_le_dossier_du_pont_au_premier_plan():
    lanceur = _Lanceur()
    assert _ouvreur(lanceur).ouvrir("Claude", "s-1", premier_plan=True)
    cmd, options = lanceur.appels[0]
    assert cmd == ["claude", "--resume", "s-1"]
    assert options["cwd"] == "D:/repo"
    assert ho.affichage(options) == ho.SW_SHOWNORMAL


def test_hors_premier_plan_la_console_s_ouvre_reduite_sans_voler_le_focus():
    lanceur = _Lanceur()
    _ouvreur(lanceur).ouvrir("Codex", "th-1", premier_plan=False)
    assert ho.affichage(lanceur.appels[0][1]) == ho.SW_SHOWMINNOACTIVE


def test_une_nouvelle_reponse_remplace_la_console_precedente_du_harnais():
    lanceur = _Lanceur()
    ouvreur = _ouvreur(lanceur)
    ouvreur.ouvrir("Claude", "s-1", premier_plan=True)
    ouvreur.ouvrir("Codex", "th-1", premier_plan=True)
    ouvreur.ouvrir("Claude", "s-1", premier_plan=True)
    assert lanceur.fermes == [1]
    assert len(lanceur.appels) == 3


def test_le_choix_premier_plan_est_retenu_et_actif_par_defaut():
    assert normaliser_configuration({}).harnais_premier_plan is True
    assert normaliser_configuration({"harnais_premier_plan": False}).harnais_premier_plan is False


def test_presence_relaye_la_session_du_harnais():
    import pytest

    pytest.importorskip("tkinter")
    from native.presence.app import relayer_harnais

    recu = []
    assert relayer_harnais({"type": "harnais_session", "harnais": "Claude", "session": "s-1"}, recu.append)
    assert recu == [{"type": "harnais_session", "harnais": "Claude", "session": "s-1"}]
    assert not relayer_harnais({"type": "autre"}, recu.append)


def test_la_console_n_herite_pas_d_un_terminal_dumb(monkeypatch):
    """Codex avertit « dumb mode » si TERM=dumb fuit d'un shell parent."""
    monkeypatch.setenv("TERM", "dumb")
    assert "TERM" not in ho.options_console("D:/repo", True)["env"]


def test_la_console_s_ouvre_dans_le_dossier_de_la_session():
    """Claude ne reprend une session que depuis son dossier (autre projet : autre dossier)."""
    lanceur = _Lanceur()
    ouvreur = ho.OuvreurHarnais(
        racine="D:/repo", lancer=lanceur.lancer, fermer=lanceur.fermer, exe=lambda n: n,
        dossier_de=lambda h, s: "D:/autre" if s == "s-autre" else None,
    )
    ouvreur.ouvrir("Claude", "s-autre", premier_plan=True)
    ouvreur.ouvrir("Codex", "th-1", premier_plan=True)
    assert lanceur.appels[0][1]["cwd"] == "D:/autre"
    assert lanceur.appels[1][1]["cwd"] == "D:/repo"
