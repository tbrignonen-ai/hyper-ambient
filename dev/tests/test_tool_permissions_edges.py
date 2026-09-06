"""
GATE: branches de permission.py hors de la table deja parametree.

test_tool_permissions.py couvre la table (mode, danger) et ask avec/sans
resolver. Ici : mode inconnu, danger inconnu, resolver qui leve, journal
d'audit qui leve, bascule de mode, describe, can_execute (deprecated),
should_log_verbose, allows_fallback.
"""
import asyncio
from dataclasses import FrozenInstanceError

import pytest

from src.gate.audit import AuditLog
from src.gate.permission import Gate, PermissionDecision, PermissionRequest


def _run(coro):
    return asyncio.run(coro)


def _req(**kw):
    base = dict(tool="web_search", arguments={"q": "paris"}, danger="read", caller="test")
    base.update(kw)
    return PermissionRequest(**base)


def test_mode_inconnu_bascule_sur_auto():
    gate = Gate(mode="nexiste-pas")
    assert gate.mode == "auto"
    decision = _run(gate.check(_req(danger="exec")))
    assert decision.allowed is True
    assert decision.mode == "auto"


def test_danger_inconnu_est_refuse_avec_motif_prononcable():
    gate = Gate(mode="auto")
    decision = _run(gate.check(_req(danger="nuke")))
    assert decision.allowed is False
    assert decision.mode == "auto"
    assert "nuke" in decision.reason
    assert "auto" in decision.reason
    assert len(decision.reason.strip()) > 5


def test_ask_resolver_qui_leve_refuse_sans_traceback():
    async def boom(request):
        raise RuntimeError("resolver exploded")

    gate = Gate(mode="ask", resolver=boom)
    decision = _run(gate.check(_req()))
    assert decision.allowed is False
    assert decision.mode == "ask"
    assert "approbation" in decision.reason.lower() or "erreur" in decision.reason.lower()
    assert "exploded" not in decision.reason
    assert "Traceback" not in decision.reason
    assert "RuntimeError" not in decision.reason


def test_ask_resolver_recoit_la_requete_complete():
    seen = {}

    async def resolver(request):
        seen["tool"] = request.tool
        seen["arguments"] = dict(request.arguments)
        seen["danger"] = request.danger
        seen["caller"] = request.caller
        return True

    gate = Gate(mode="ask", resolver=resolver)
    req = _req(tool="file_write", arguments={"path": "/tmp"}, danger="write", caller="suite")
    decision = _run(gate.check(req))
    assert decision.allowed is True
    assert seen == {
        "tool": "file_write",
        "arguments": {"path": "/tmp"},
        "danger": "write",
        "caller": "suite",
    }
    assert decision.reason == "Action approuvée par l'utilisateur."


def test_ask_refus_utilisateur_a_le_motif_exact():
    async def non(request):
        return False

    decision = _run(Gate(mode="ask", resolver=non).check(_req()))
    assert decision.allowed is False
    assert decision.reason == "Action refusée par l'utilisateur."


def test_ask_sans_resolver_a_le_motif_exact():
    decision = _run(Gate(mode="ask").check(_req()))
    assert decision.allowed is False
    assert "confirmation" in decision.reason.lower() or "disponible" in decision.reason.lower()


def test_audit_qui_leve_ne_bloque_pas_la_decision(tmp_path):
    class BrokenAudit:
        async def log(self, **kwargs):
            raise OSError("disk full")

    gate = Gate(mode="auto", audit=BrokenAudit())
    decision = _run(gate.check(_req(danger="read")))
    assert decision.allowed is True
    assert decision.mode == "auto"


def test_audit_enregistre_arguments_et_motif(tmp_path):
    log_file = tmp_path / "audit.jsonl"
    audit = AuditLog(log_path=str(log_file))
    gate = Gate(mode="plan", audit=audit)
    req = _req(tool="web_search", arguments={"query": "meteo"}, danger="read")
    decision = _run(gate.check(req))
    assert decision.allowed is False
    entries = _run(audit.get_entries())
    assert len(entries) == 1
    params = entries[0]["params"]
    assert params["arguments"] == {"query": "meteo"}
    assert params["reason"] == decision.reason
    assert params["mode"] == "plan"
    assert entries[0]["result"] == "denied"


def test_audit_chaine_deux_decisions(tmp_path):
    log_file = tmp_path / "chain.jsonl"
    audit = AuditLog(log_path=str(log_file))
    gate = Gate(mode="auto", audit=audit)
    _run(gate.check(_req(tool="a")))
    _run(gate.check(_req(tool="b", danger="write")))
    entries = _run(audit.get_entries())
    assert len(entries) == 2
    assert entries[1]["prev_hash"] == entries[0]["hash"]
    assert _run(audit.verify_chain()) is True


def test_set_mode_valide_change_la_politique():
    gate = Gate(mode="auto")
    _run(gate.set_mode("plan"))
    assert gate.mode == "plan"
    decision = _run(gate.check(_req(danger="read")))
    assert decision.allowed is False
    assert decision.mode == "plan"


def test_set_mode_invalide_ne_change_rien():
    gate = Gate(mode="build")
    _run(gate.set_mode("nexiste-pas"))
    assert gate.mode == "build"


def test_describe_couvre_tous_les_modes():
    for mode in sorted(Gate.MODES):
        text = Gate(mode=mode).describe()
        assert isinstance(text, str) and text.strip()
        assert text != "Unknown mode"


def test_should_log_verbose_seulement_build_et_troubleshoot():
    verbose = {mode: Gate(mode=mode).should_log_verbose() for mode in Gate.MODES}
    assert verbose["build"] is True
    assert verbose["troubleshoot"] is True
    assert verbose["auto"] is False
    assert verbose["yolo"] is False
    assert verbose["plan"] is False
    assert verbose["ask"] is False
    assert verbose["manual"] is False


def test_allows_fallback_partout_sauf_yolo():
    for mode in Gate.MODES:
        allowed = Gate(mode=mode).allows_fallback()
        if mode == "yolo":
            assert allowed is False
        else:
            assert allowed is True


def test_can_execute_yolo_toujours_vrai():
    gate = Gate(mode="yolo")
    with pytest.deprecated_call():
        assert gate.can_execute("anything", requires_approval=True) is True


def test_can_execute_ask_avec_approbation_refuse():
    gate = Gate(mode="ask")
    with pytest.deprecated_call():
        assert gate.can_execute("web_search", requires_approval=True) is False


def test_can_execute_ask_sans_approbation_refuse_quand_meme():
    gate = Gate(mode="ask")
    with pytest.deprecated_call():
        assert gate.can_execute("web_search", requires_approval=False) is False


def test_can_execute_manual_refuse():
    gate = Gate(mode="manual")
    with pytest.deprecated_call():
        assert gate.can_execute("web_search") is False


def test_can_execute_build_autorise():
    gate = Gate(mode="build")
    with pytest.deprecated_call():
        assert gate.can_execute("web_search") is True


def test_policy_table_couvre_tous_les_modes_sauf_ask():
    dangers = ("read", "write", "exec")
    for mode in Gate.MODES:
        if mode == "ask":
            continue
        for danger in dangers:
            assert (mode, danger) in Gate.POLICY_TABLE, f"manque {(mode, danger)}"


def test_motifs_de_la_table_sont_ceux_rendus():
    gate = Gate(mode="plan")
    decision = _run(gate.check(_req(danger="write")))
    allowed, reason = Gate.POLICY_TABLE[("plan", "write")]
    assert decision.allowed is allowed
    assert decision.reason == reason


def test_permission_request_est_figee():
    req = _req()
    with pytest.raises(FrozenInstanceError):
        req.tool = "autre"


def test_permission_decision_est_figee():
    decision = PermissionDecision(True, "ok", "auto")
    with pytest.raises(FrozenInstanceError):
        decision.allowed = False


def test_caller_par_defaut_est_la_boucle():
    req = PermissionRequest(tool="t", arguments={}, danger="read")
    assert req.caller == "brain.tool_loop"


def test_modes_sont_les_sept_attendus():
    assert Gate.MODES == {"plan", "ask", "manual", "auto", "build", "troubleshoot", "yolo"}


def test_defaut_constructeur_est_auto():
    assert Gate().mode == "auto"


def test_get_entries_fichier_absent(tmp_path):
    audit = AuditLog(log_path=str(tmp_path / "missing" / "audit.jsonl"))
    assert _run(audit.get_entries()) == []
    assert _run(audit.verify_chain()) is True
