"""
GATE: deuxieme nappe d'edges pour permission.py + audit.py (vague F).

La nappe D couvre mode inconnu, danger inconnu, resolver qui leve, audit
disque plein, describe, can_execute partiel. Ici : la table complete des
motifs, ask qui ignore / accepte un truthy non-bool, auto qui n'appelle
pas le resolver, can_execute restant, describe apres mutation, chaine
d'audit faussee, get_entries borne / JSON pourri.
asyncio.run — pas de pytest-asyncio.
"""
import asyncio
import json
import warnings

import pytest

from src.gate.audit import AuditLog
from src.gate.permission import Gate, PermissionRequest


def _run(coro):
    return asyncio.run(coro)


def _req(**kw):
    base = dict(tool="web_search", arguments={"q": "paris"}, danger="read", caller="test")
    base.update(kw)
    return PermissionRequest(**base)


# Motifs exacts de POLICY_TABLE — une derive de copy les ferait parler faux.
_RAISONS = {
    ("auto", "read"): (True, "Lecture autorisée."),
    ("auto", "write"): (True, "Écriture autorisée."),
    ("auto", "exec"): (True, "Exécution autorisée."),
    ("plan", "read"): (False, "Mode simulation actif, lecture non exécutée."),
    ("plan", "write"): (False, "Mode simulation actif, écriture non exécutée."),
    ("plan", "exec"): (False, "Mode simulation actif, exécution non effectuée."),
    ("manual", "read"): (False, "Action en attente de déclenchement manuel."),
    ("manual", "write"): (False, "Action en attente de déclenchement manuel."),
    ("manual", "exec"): (False, "Action en attente de déclenchement manuel."),
    ("build", "read"): (True, "Lecture autorisée en mode développement."),
    ("build", "write"): (True, "Écriture autorisée en mode développement."),
    ("build", "exec"): (True, "Exécution autorisée en mode développement."),
    ("troubleshoot", "read"): (True, "Lecture autorisée en mode diagnostic."),
    ("troubleshoot", "write"): (True, "Écriture autorisée en mode diagnostic."),
    ("troubleshoot", "exec"): (True, "Exécution autorisée en mode diagnostic."),
    ("yolo", "read"): (True, "Lecture autorisée."),
    ("yolo", "write"): (True, "Écriture autorisée."),
    ("yolo", "exec"): (True, "Exécution autorisée."),
}


def test_policy_table_motifs_exacts_sur_les_dix_huit_cellules():
    assert set(Gate.POLICY_TABLE) == set(_RAISONS)
    for (mode, danger), (allowed, reason) in _RAISONS.items():
        assert Gate.POLICY_TABLE[(mode, danger)] == (allowed, reason)
        decision = _run(Gate(mode=mode).check(_req(danger=danger)))
        assert decision.allowed is allowed, (mode, danger)
        assert decision.reason == reason
        assert decision.mode == mode


def test_ask_n_est_pas_dans_la_table():
    for danger in ("read", "write", "exec"):
        assert ("ask", danger) not in Gate.POLICY_TABLE


def test_auto_n_appelle_pas_le_resolver():
    seen = []

    async def resolver(request):
        seen.append(request)
        return False

    decision = _run(Gate(mode="auto", resolver=resolver).check(_req(danger="exec")))
    assert seen == []
    assert decision.allowed is True
    assert decision.mode == "auto"


def test_ask_resolver_truthy_non_bool_autorise():
    async def resolver(request):
        return 1

    decision = _run(Gate(mode="ask", resolver=resolver).check(_req()))
    assert decision.allowed is True
    assert decision.reason == "Action approuvée par l'utilisateur."


def test_ask_resolver_none_est_un_refus_utilisateur():
    async def resolver(request):
        return None

    decision = _run(Gate(mode="ask", resolver=resolver).check(_req()))
    assert decision.allowed is False
    assert decision.reason == "Action refusée par l'utilisateur."


def test_ask_resolver_chaine_vide_est_un_refus():
    async def resolver(request):
        return ""

    decision = _run(Gate(mode="ask", resolver=resolver).check(_req()))
    assert decision.allowed is False
    assert decision.reason == "Action refusée par l'utilisateur."


def test_set_mode_vers_ask_sans_resolver_refuse_ensuite():
    gate = Gate(mode="auto")
    _run(gate.set_mode("ask"))
    assert gate.mode == "ask"
    decision = _run(gate.check(_req(danger="read")))
    assert decision.allowed is False
    assert "confirmation" in decision.reason.lower() or "disponible" in decision.reason.lower()


def test_set_mode_identite_reste_stable():
    gate = Gate(mode="yolo")
    _run(gate.set_mode("yolo"))
    assert gate.mode == "yolo"
    assert _run(gate.check(_req(danger="exec"))).allowed is True


def test_set_mode_chaine_vide_ne_change_rien():
    gate = Gate(mode="manual")
    _run(gate.set_mode(""))
    assert gate.mode == "manual"


def test_audit_absent_ne_bloque_pas():
    gate = Gate(mode="plan", audit=None)
    decision = _run(gate.check(_req(danger="write")))
    assert decision.allowed is False
    assert decision.reason == Gate.POLICY_TABLE[("plan", "write")][1]


def test_audit_qui_leve_sur_un_refus_rend_quand_meme_le_refus():
    class BrokenAudit:
        async def log(self, **kwargs):
            raise OSError("disk full")

    gate = Gate(mode="plan", audit=BrokenAudit())
    decision = _run(gate.check(_req(danger="exec")))
    assert decision.allowed is False
    assert decision.mode == "plan"


def test_ask_autorise_est_journalise_allowed(tmp_path):
    async def oui(request):
        return True

    audit = AuditLog(log_path=str(tmp_path / "ask.jsonl"))
    gate = Gate(mode="ask", audit=audit, resolver=oui)
    decision = _run(gate.check(_req(tool="web_search", danger="read")))
    assert decision.allowed is True
    entries = _run(audit.get_entries())
    assert entries[0]["result"] == "allowed"
    assert entries[0]["action"] == "tool_call"
    assert entries[0]["params"]["mode"] == "ask"
    assert entries[0]["user_id"] == "anonymous"


def test_check_n_ecrase_pas_le_danger_de_la_requete():
    gate = Gate(mode="auto")
    req = _req(danger="write")
    _run(gate.check(req))
    assert req.danger == "write"


def test_arguments_internes_restent_mutables_malgre_frozen():
    """frozen protege les champs, pas le dict qu'ils pointent — a ne pas traiter comme un coffre."""
    req = _req(arguments={"q": "a"})
    req.arguments["q"] = "b"
    assert req.arguments["q"] == "b"


def test_describe_inconnu_apres_mutation():
    gate = Gate(mode="auto")
    gate.mode = "???"
    assert gate.describe() == "Unknown mode"


def test_can_execute_auto_et_troubleshoot_autorisent():
    with pytest.deprecated_call():
        assert Gate(mode="auto").can_execute("web_search") is True
    with pytest.deprecated_call():
        assert Gate(mode="troubleshoot").can_execute("web_search") is True


def test_can_execute_plan_refuse_meme_sans_approbation():
    with pytest.deprecated_call():
        assert Gate(mode="plan").can_execute("web_search", requires_approval=False) is False


def test_can_execute_mode_muté_inconnu_refuse():
    gate = Gate(mode="auto")
    gate.mode = "???"
    with pytest.deprecated_call():
        assert gate.can_execute("web_search") is False


def test_can_execute_emet_deprecation_warning():
    gate = Gate(mode="auto")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        gate.can_execute("x")
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert any("check" in str(w.message).lower() for w in caught)


def test_should_log_verbose_apres_set_mode():
    gate = Gate(mode="auto")
    assert gate.should_log_verbose() is False
    _run(gate.set_mode("build"))
    assert gate.should_log_verbose() is True
    _run(gate.set_mode("yolo"))
    assert gate.should_log_verbose() is False
    assert gate.allows_fallback() is False


def test_yolo_autorise_exec_mais_coupe_le_repli():
    gate = Gate(mode="yolo")
    decision = _run(gate.check(_req(danger="exec")))
    assert decision.allowed is True
    assert gate.allows_fallback() is False


def test_verify_chain_detecte_un_hash_falsifie(tmp_path):
    path = tmp_path / "tamper.jsonl"
    audit = AuditLog(log_path=str(path))
    _run(audit.log(action="tool_call", params={"n": 1}, result="allowed", caller="t"))
    lines = path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["hash"] = "0" * 64
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    assert _run(audit.verify_chain()) is False


def test_verify_chain_detecte_un_prev_hash_casse(tmp_path):
    path = tmp_path / "break.jsonl"
    audit = AuditLog(log_path=str(path))
    _run(audit.log(action="a", params={}, result="ok", caller="t"))
    _run(audit.log(action="b", params={}, result="ok", caller="t"))
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    lines[1]["prev_hash"] = "deadbeef"
    # Recalculer un hash coherent sur le contenu fausse le lien, pas le hash local.
    stored = lines[1].pop("hash")
    recomputed = audit._compute_hash(lines[1])
    lines[1]["hash"] = recomputed
    assert stored != recomputed or lines[1]["prev_hash"] == "deadbeef"
    path.write_text(
        "".join(json.dumps(e) + "\n" for e in lines),
        encoding="utf-8",
    )
    assert _run(audit.verify_chain()) is False


def test_get_entries_honore_la_limite(tmp_path):
    path = tmp_path / "many.jsonl"
    audit = AuditLog(log_path=str(path))
    for i in range(5):
        _run(audit.log(action=f"a{i}", params={"i": i}, result="ok", caller="t"))
    last_two = _run(audit.get_entries(limit=2))
    assert len(last_two) == 2
    assert last_two[0]["params"]["i"] == 3
    assert last_two[1]["params"]["i"] == 4
    all_five = _run(audit.get_entries(limit=100))
    assert len(all_five) == 5


def test_get_entries_json_pourri_rend_liste_vide(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text("{pas du json\n", encoding="utf-8")
    audit = AuditLog(log_path=str(path))
    assert _run(audit.get_entries()) == []
    assert _run(audit.verify_chain()) is False


def test_load_last_hash_sur_fichier_corrompu_continue(tmp_path):
    path = tmp_path / "corrupt.jsonl"
    path.write_text("@@@\n", encoding="utf-8")
    audit = AuditLog(log_path=str(path))
    assert audit.last_hash is None
    _run(audit.log(action="recover", params={}, result="ok", caller="t"))
    entries = _run(audit.get_entries())
    # get_entries parse tout le fichier : la ligne pourrie fait echouer la lecture.
    assert entries == []
    assert audit.last_hash is not None
    assert _run(audit.verify_chain()) is False


def test_audit_user_id_explicite(tmp_path):
    audit = AuditLog(log_path=str(tmp_path / "u.jsonl"))
    entry = _run(audit.log(action="x", params={}, result="ok", caller="c", user_id="thomas"))
    assert entry["user_id"] == "thomas"
    assert entry["prev_hash"] is None
    assert len(entry["hash"]) == 64


def test_reprise_de_chaine_sur_fichier_existant(tmp_path):
    path = tmp_path / "resume.jsonl"
    first = AuditLog(log_path=str(path))
    _run(first.log(action="one", params={}, result="ok", caller="t"))
    second = AuditLog(log_path=str(path))
    assert second.last_hash == first.last_hash
    _run(second.log(action="two", params={}, result="ok", caller="t"))
    entries = _run(second.get_entries())
    assert len(entries) == 2
    assert entries[1]["prev_hash"] == entries[0]["hash"]
    assert _run(second.verify_chain()) is True


def test_motifs_de_refus_sont_prononcables_sans_code():
    for mode in ("plan", "manual"):
        reason = _run(Gate(mode=mode).check(_req(danger="exec"))).reason
        assert "{" not in reason
        assert "None" not in reason
        assert "\n" not in reason
        assert len(reason) > 10
