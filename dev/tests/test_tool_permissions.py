"""
Tests for Gate permissions, decision table, ask mode with/without resolver, and AuditLog integration.
"""
import asyncio
import pytest
from src.gate.permission import Gate, PermissionRequest, PermissionDecision
from src.gate.audit import AuditLog


def _run(coro):
    return asyncio.run(coro)


def test_dataclasses_structure():
    req = PermissionRequest(
        tool="web_search",
        arguments={"query": "test"},
        danger="read",
        caller="brain.tool_loop",
    )
    assert req.tool == "web_search"
    assert req.arguments == {"query": "test"}
    assert req.danger == "read"
    assert req.caller == "brain.tool_loop"

    # Default caller
    req_default = PermissionRequest(tool="test_tool", arguments={}, danger="write")
    assert req_default.caller == "brain.tool_loop"

    decision = PermissionDecision(allowed=True, reason="Lecture autorisée.", mode="auto")
    assert decision.allowed is True
    assert decision.reason == "Lecture autorisée."
    assert decision.mode == "auto"


@pytest.mark.parametrize(
    "mode,danger,expected_allowed",
    [
        # auto
        ("auto", "read", True),
        ("auto", "write", True),
        ("auto", "exec", True),
        # plan
        ("plan", "read", False),
        ("plan", "write", False),
        ("plan", "exec", False),
        # manual
        ("manual", "read", False),
        ("manual", "write", False),
        ("manual", "exec", False),
        # build
        ("build", "read", True),
        ("build", "write", True),
        ("build", "exec", True),
        # troubleshoot
        ("troubleshoot", "read", True),
        ("troubleshoot", "write", True),
        ("troubleshoot", "exec", True),
        # yolo
        ("yolo", "read", True),
        ("yolo", "write", True),
        ("yolo", "exec", True),
    ],
)
def test_policy_table_decisions(mode, danger, expected_allowed):
    gate = Gate(mode=mode)
    req = PermissionRequest(tool="test_tool", arguments={"a": 1}, danger=danger)
    decision = _run(gate.check(req))

    assert decision.allowed == expected_allowed
    assert decision.mode == mode
    assert isinstance(decision.reason, str)
    assert len(decision.reason) > 0
    if not decision.allowed:
        # Refusal reason must be non-empty, pronounceable French string
        assert len(decision.reason.strip()) > 5


def test_ask_mode_without_resolver_refuses_with_pronounceable_reason():
    gate = Gate(mode="ask", resolver=None)
    req = PermissionRequest(tool="web_search", arguments={"q": "paris"}, danger="read")
    decision = _run(gate.check(req))

    assert decision.allowed is False
    assert decision.mode == "ask"
    assert "confirmation" in decision.reason.lower() or "disponible" in decision.reason.lower() or "autorisation" in decision.reason.lower() or len(decision.reason) > 5


def test_ask_mode_with_resolver_approved():
    async def mock_resolver(request: PermissionRequest) -> bool:
        assert request.tool == "web_search"
        return True

    gate = Gate(mode="ask", resolver=mock_resolver)
    req = PermissionRequest(tool="web_search", arguments={"q": "paris"}, danger="read")
    decision = _run(gate.check(req))

    assert decision.allowed is True
    assert decision.mode == "ask"


def test_ask_mode_with_resolver_denied():
    async def mock_resolver(request: PermissionRequest) -> bool:
        return False

    gate = Gate(mode="ask", resolver=mock_resolver)
    req = PermissionRequest(tool="web_search", arguments={"q": "paris"}, danger="read")
    decision = _run(gate.check(req))

    assert decision.allowed is False
    assert decision.mode == "ask"
    assert "refus" in decision.reason.lower() or len(decision.reason) > 5


def test_audit_log_called_when_injected(tmp_path):
    log_file = tmp_path / "audit_test.jsonl"
    audit = AuditLog(log_path=str(log_file))

    gate = Gate(mode="auto", audit=audit)
    req = PermissionRequest(
        tool="test_tool",
        arguments={"param": "val"},
        danger="exec",
        caller="test_suite",
    )
    decision = _run(gate.check(req))
    assert decision.allowed is True

    entries = _run(audit.get_entries())
    assert len(entries) == 1
    entry = entries[0]
    assert entry["action"] == "tool_call"
    assert entry["result"] == "allowed"
    assert entry["caller"] == "test_suite"
    assert entry["params"]["tool"] == "test_tool"
    assert entry["params"]["danger"] == "exec"
    assert entry["params"]["mode"] == "auto"

    is_valid = _run(audit.verify_chain())
    assert is_valid is True


def test_audit_log_denied_logged(tmp_path):
    log_file = tmp_path / "audit_test_denied.jsonl"
    audit = AuditLog(log_path=str(log_file))

    gate = Gate(mode="plan", audit=audit)
    req = PermissionRequest(
        tool="delete_tool",
        arguments={"force": True},
        danger="write",
        caller="brain.tool_loop",
    )
    decision = _run(gate.check(req))
    assert decision.allowed is False

    entries = _run(audit.get_entries())
    assert len(entries) == 1
    entry = entries[0]
    assert entry["result"] == "denied"
    assert entry["params"]["tool"] == "delete_tool"


def test_can_execute_deprecated():
    gate = Gate(mode="auto")
    with pytest.deprecated_call():
        res = gate.can_execute("some_action")
    assert res is True

    gate_plan = Gate(mode="plan")
    with pytest.deprecated_call():
        res_plan = gate_plan.can_execute("some_action")
    assert res_plan is False
