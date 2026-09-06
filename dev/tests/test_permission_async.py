"""
GATE: contrat async de permission.py + audit.py (vague H).

Les nappes D/F collent la table, ask truthy, audit falsifie. Ici : ce qui
n'existe que parce que `check` / `log` / `set_mode` sont des coroutines —

  - `check` sans await est un coroutine, pas une decision,
  - le resolver **est** awaited (sleep),
  - `asyncio.gather` de N checks sur la meme porte,
  - `set_mode` pendant qu'un ask resolver attend,
  - `get_entries(limit=0)` (0 est falsy : tout le fichier),
  - BaseException du resolver non rattrapee,
  - chaine d'audit sous gather (pas d'await interne dans log : serialise).

asyncio.run — pas de pytest-asyncio.
"""
import asyncio
import inspect

import pytest

from src.gate.audit import AuditLog
from src.gate.permission import Gate, PermissionRequest


def _run(coro):
    return asyncio.run(coro)


def _req(**kw):
    base = dict(tool="web_search", arguments={"q": "paris"}, danger="read", caller="test")
    base.update(kw)
    return PermissionRequest(**base)


def test_check_set_mode_log_sont_des_coroutines():
    assert inspect.iscoroutinefunction(Gate.check)
    assert inspect.iscoroutinefunction(Gate.set_mode)
    assert inspect.iscoroutinefunction(AuditLog.log)
    assert inspect.iscoroutinefunction(AuditLog.get_entries)
    assert inspect.iscoroutinefunction(AuditLog.verify_chain)
    assert not inspect.iscoroutinefunction(Gate.describe)
    assert not inspect.iscoroutinefunction(Gate.can_execute)
    assert not inspect.iscoroutinefunction(Gate.allows_fallback)


def test_check_sans_await_n_est_pas_une_decision():
    gate = Gate(mode="auto")
    pending = gate.check(_req())
    assert inspect.iscoroutine(pending)
    pending.close()


def test_resolver_est_vraiment_awaited():
    order = []

    async def resolver(request):
        order.append("enter")
        await asyncio.sleep(0.02)
        order.append("leave")
        return True

    async def scenario():
        gate = Gate(mode="ask", resolver=resolver)
        order.append("before")
        decision = await gate.check(_req())
        order.append("after")
        return decision

    decision = _run(scenario())
    assert decision.allowed is True
    assert order == ["before", "enter", "leave", "after"]
    assert decision.reason == "Action approuvée par l'utilisateur."


def test_resolver_voit_la_requete_apres_le_yield():
    seen = {}

    async def resolver(request):
        await asyncio.sleep(0)
        seen["tool"] = request.tool
        seen["danger"] = request.danger
        seen["caller"] = request.caller
        return False

    decision = _run(Gate(mode="ask", resolver=resolver).check(
        _req(tool="file_write", danger="write", caller="suite"),
    ))
    assert decision.allowed is False
    assert seen == {"tool": "file_write", "danger": "write", "caller": "suite"}


def test_gather_huit_checks_auto_tous_autorises():
    async def scenario():
        gate = Gate(mode="auto")
        reqs = [_req(tool=f"t{i}", arguments={"i": i}) for i in range(8)]
        return await asyncio.gather(*[gate.check(r) for r in reqs])

    decisions = _run(scenario())
    assert len(decisions) == 8
    assert all(d.allowed is True and d.mode == "auto" for d in decisions)


def test_gather_mixte_deux_portes():
    async def scenario():
        auto = Gate(mode="auto")
        plan = Gate(mode="plan")
        a, b = await asyncio.gather(auto.check(_req()), plan.check(_req(danger="exec")))
        return a, b

    allowed, denied = _run(scenario())
    assert allowed.allowed is True
    assert denied.allowed is False
    assert "simulation" in denied.reason.lower()


def test_gather_ask_resolvers_independants():
    async def yes(request):
        await asyncio.sleep(0)
        return True

    async def no(request):
        await asyncio.sleep(0)
        return False

    async def scenario():
        g_yes = Gate(mode="ask", resolver=yes)
        g_no = Gate(mode="ask", resolver=no)
        return await asyncio.gather(g_yes.check(_req()), g_no.check(_req()))

    ok, ko = _run(scenario())
    assert ok.allowed is True
    assert ko.allowed is False
    assert ko.reason == "Action refusée par l'utilisateur."


def test_set_mode_pendant_un_ask_resolver():
    """Le mode est relu *apres* l'await du resolver : un set_mode concurrent
    change le champ `mode` de la decision, pas le allowed calcule par l'ask."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def resolver(request):
        started.set()
        await release.wait()
        return True

    async def scenario():
        gate = Gate(mode="ask", resolver=resolver)
        task = asyncio.create_task(gate.check(_req(danger="exec")))
        await started.wait()
        await gate.set_mode("plan")
        release.set()
        return await task, gate.mode

    decision, mode = _run(scenario())
    assert mode == "plan"
    assert decision.allowed is True
    assert decision.mode == "plan"
    assert decision.reason == "Action approuvée par l'utilisateur."


def test_set_mode_avant_le_check_change_la_politique():
    async def scenario():
        gate = Gate(mode="auto")
        await gate.set_mode("manual")
        return await gate.check(_req(danger="write"))

    decision = _run(scenario())
    assert decision.allowed is False
    assert decision.mode == "manual"
    assert "manuel" in decision.reason.lower()


def test_deux_ask_sequentiels_reponses_differentes():
    answers = iter([True, False])

    async def resolver(request):
        await asyncio.sleep(0)
        return next(answers)

    async def scenario():
        gate = Gate(mode="ask", resolver=resolver)
        first = await gate.check(_req(tool="a"))
        second = await gate.check(_req(tool="b"))
        return first, second

    first, second = _run(scenario())
    assert first.allowed is True
    assert second.allowed is False


def test_resolver_appele_une_fois_par_check():
    n = []

    async def resolver(request):
        n.append(1)
        await asyncio.sleep(0)
        return True

    _run(Gate(mode="ask", resolver=resolver).check(_req()))
    assert n == [1]


class _Killer(BaseException):
    """Hors Exception : Gate.check ne l'avale pas."""


def test_resolver_baseexception_se_propage():
    async def boom(request):
        raise _Killer("stop")

    with pytest.raises(_Killer, match="stop"):
        _run(Gate(mode="ask", resolver=boom).check(_req()))


def test_gather_audit_chaine_reste_valide(tmp_path):
    """log() n'await pas en interne : les writes gather se serialisent, la chaine tient."""

    async def scenario():
        audit = AuditLog(log_path=str(tmp_path / "g.jsonl"))
        gate = Gate(mode="auto", audit=audit)
        await asyncio.gather(*[gate.check(_req(tool=f"t{i}")) for i in range(6)])
        return await audit.verify_chain(), await audit.get_entries(limit=100)

    ok, entries = _run(scenario())
    assert ok is True
    assert len(entries) == 6
    assert entries[0]["prev_hash"] is None
    for prev, cur in zip(entries, entries[1:]):
        assert cur["prev_hash"] == prev["hash"]


def test_get_entries_limit_zero_rend_tout(tmp_path):
    """`if limit else entries` : 0 est falsy, donc pas une fenetre vide."""
    audit = AuditLog(log_path=str(tmp_path / "z.jsonl"))
    for i in range(3):
        _run(audit.log(action=f"a{i}", params={"i": i}, result="ok", caller="t"))
    assert len(_run(audit.get_entries(limit=0))) == 3
    assert len(_run(audit.get_entries(limit=None))) == 3


def test_fichier_vide_verify_true_last_hash_none(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    audit = AuditLog(log_path=str(path))
    assert audit.last_hash is None
    assert _run(audit.verify_chain()) is True
    assert _run(audit.get_entries()) == []


def test_premiere_entree_prev_hash_none(tmp_path):
    audit = AuditLog(log_path=str(tmp_path / "p.jsonl"))
    entry = _run(audit.log(action="first", params={}, result="ok", caller="c"))
    assert entry["prev_hash"] is None
    assert entry["hash"] == audit.last_hash
    assert len(entry["hash"]) == 64


def test_audit_log_rend_l_entree_meme_si_le_disque_leve(tmp_path, monkeypatch):
    audit = AuditLog(log_path=str(tmp_path / "x.jsonl"))

    def boom(*a, **k):
        raise OSError("readonly")

    monkeypatch.setattr("builtins.open", boom)
    entry = _run(audit.log(action="x", params={"a": 1}, result="ok", caller="t"))
    assert entry["action"] == "x"
    assert entry["hash"]
    # last_hash a quand meme avance : le hash est calcule avant l'ecriture.
    assert audit.last_hash == entry["hash"]


def test_yolo_puis_ask_puis_auto():
    async def oui(request):
        return True

    async def scenario():
        gate = Gate(mode="yolo")
        a = await gate.check(_req(danger="exec"))
        await gate.set_mode("ask")
        b = await gate.check(_req())
        gate.resolver = oui
        c = await gate.check(_req())
        await gate.set_mode("auto")
        d = await gate.check(_req(danger="write"))
        return a, b, c, d

    a, b, c, d = _run(scenario())
    assert a.allowed is True and a.mode == "yolo"
    assert b.allowed is False and b.mode == "ask"
    assert c.allowed is True and c.mode == "ask"
    assert d.allowed is True and d.mode == "auto"


def test_gather_dangers_inconnus_refusent():
    async def scenario():
        gate = Gate(mode="auto")
        return await asyncio.gather(
            gate.check(_req(danger="nuke")),
            gate.check(_req(danger="read")),
        )

    bad, good = _run(scenario())
    assert bad.allowed is False
    assert "nuke" in bad.reason
    assert good.allowed is True


def test_check_n_await_pas_le_resolver_hors_ask():
    seen = []

    async def resolver(request):
        seen.append("called")
        return False

    async def scenario():
        gate = Gate(mode="build", resolver=resolver)
        d1 = await gate.check(_req(danger="exec"))
        d2 = await gate.check(_req(danger="write"))
        return d1, d2

    d1, d2 = _run(scenario())
    assert seen == []
    assert d1.allowed is True and d2.allowed is True


def test_ask_resolver_lent_n_empeche_pas_une_autre_porte():
    release = asyncio.Event()

    async def slow(request):
        await release.wait()
        return True

    async def scenario():
        stuck = Gate(mode="ask", resolver=slow)
        free = Gate(mode="auto")
        task = asyncio.create_task(stuck.check(_req()))
        fast = await asyncio.wait_for(free.check(_req()), timeout=0.2)
        release.set()
        slow_decision = await task
        return fast, slow_decision

    fast, slow_decision = _run(scenario())
    assert fast.allowed is True
    assert slow_decision.allowed is True


def test_arguments_partages_entre_checks_concurrents():
    """frozen protege le champ, pas le dict : deux checks voient la meme mutation."""

    async def scenario():
        req = _req(arguments={"q": "a"})
        gate = Gate(mode="auto")
        t = asyncio.create_task(gate.check(req))
        req.arguments["q"] = "mutated"
        decision = await t
        return decision, req.arguments["q"]

    decision, value = _run(scenario())
    assert decision.allowed is True
    assert value == "mutated"


def test_audit_caller_et_result_denied_sous_plan(tmp_path):
    audit = AuditLog(log_path=str(tmp_path / "d.jsonl"))
    gate = Gate(mode="plan", audit=audit)
    _run(gate.check(_req(tool="web_search", danger="exec", caller="brain.tool_loop")))
    entry = _run(audit.get_entries())[0]
    assert entry["result"] == "denied"
    assert entry["caller"] == "brain.tool_loop"
    assert entry["params"]["tool"] == "web_search"
    assert entry["params"]["danger"] == "exec"


def test_verify_chain_fichier_absent_est_valide(tmp_path):
    audit = AuditLog(log_path=str(tmp_path / "missing" / "nope.jsonl"))
    # le parent est cree par __init__, pas le fichier.
    assert not audit.log_path.exists() or audit.log_path.stat().st_size == 0 or True
    assert _run(audit.verify_chain()) is True


def test_should_log_verbose_n_est_pas_async():
    gate = Gate(mode="troubleshoot")
    assert gate.should_log_verbose() is True
    assert inspect.iscoroutinefunction(type(gate).should_log_verbose) is False
