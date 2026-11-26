import json
import warnings

import pytest

warnings.filterwarnings("ignore")

from cov import engine
from cov.agent import RuleInvestigator, Toolbox
from cov.approval import ApprovalGate, AuthorityError
from cov.audit import AuditLog
from cov.common import DATA
from cov.extract import RuleExtractor
from cov.kg import build_all, resolve_terms
from cov.memo import numeric_guard
from cov.pipeline import Monitor
from datagen.generate import terms_at
from datagen.spec import BORROWERS, TEST_PERIODS

KEY = json.loads((DATA / "gold" / "answer_key.json").read_text())
GRAPHS = build_all()


def test_worked_example_from_midpoint():
    """Midpoint report worked case: 4.08x claimed vs 4.35x engine, governing 4.25x -> breach."""
    t = resolve_terms(GRAPHS["AIH"], "2025-09-30")
    assert t.lev_threshold == 4.25 and t.versions == ["BASE", "AMD1"]
    e = engine.run(t, {"ebitda_pre": 40000, "debt_basis_amount": 220000, "cash": 20000, "interest": 8000,
                       "capex": 0, "cash_taxes": 0, "principal": 0},
                   {"Non-Recurring Charges": 5000, "Pro Forma Cost Savings": 4000})
    assert e.cons_ebitda == 46000 and e.addbacks_permitted == 6000
    assert round(e.lev_ratio, 2) == 4.35 and e.status == "BREACH"
    assert round(e.ebitda_change_to_threshold) == 1059 and round(e.debt_change_to_threshold) == 4500


@pytest.mark.parametrize("row", KEY,
                         ids=lambda r: f"{r['borrower']}-{r['period']}")
def test_engine_matches_answer_key(row):
    t = resolve_terms(GRAPHS[row["borrower"]], row["period"])
    if t.halt:
        return
    claims = {k: v["claimed"] for k, v in row["addbacks"].items()}
    e = engine.run(t, {"ebitda_pre": row["ebitda_pre"], "debt_basis_amount": row["debt_basis"],
                       "cash": row["cash_netted"],
                       "interest": row["interest"], "capex": row["capex"], "cash_taxes": row["cash_taxes"],
                       "principal": row["principal"]}, claims)
    assert abs(e.cons_ebitda - row["cons_ebitda"]) < 1e-6
    assert abs(e.lev_ratio - row["lev_ratio"]) < 1e-9
    assert abs(e.cov_ratio - row["cov_ratio"]) < 1e-9
    assert e.status == row["truth_status"]


@pytest.mark.parametrize("bid", list(BORROWERS))
def test_governing_version_resolution(bid):
    for p in TEST_PERIODS:
        t, truth = resolve_terms(GRAPHS[bid], p), terms_at(BORROWERS[bid], p)
        assert bool(t.halt) == bool(truth["halt"])
        if not t.halt:
            assert t.lev_threshold == truth["lev_threshold"]
            assert set(t.addbacks) == set(truth["addbacks"])


def test_missing_effective_date_halts():
    t = resolve_terms(GRAPHS["CLC"], "2026-06-30")
    assert t.halt and "no determinable effective date" in t.halt


def test_injected_text_in_numeric_field_is_not_guessed():
    ex = RuleExtractor().extract("DSW", "2026-06-30", DATA / "borrowers/DSW/packages/2026-06-30")
    f = ex.fields["cert.addback::Stock-Based Compensation"]
    assert f.value is None and f.status == "anomaly"


def test_agent_never_sees_free_text():
    m = Monitor(audit_path="/tmp/test_audit.jsonl")
    m.run("AIH", "2025-09-30")
    r = m.run("AIH", "2025-12-31")  # certificate carries an embedded instruction
    blob = json.dumps(r["agent_trace"], default=str)
    assert "AUTOMATED REVIEW" not in blob and "COMPLIANT" not in blob
    assert r["free_text_for_analyst"] and r["provisional_status"] == "BREACH"


def test_injection_twin_identical():
    for case in json.loads((DATA / "gold" / "injection_twins.json").read_text()):
        a = Monitor(audit_path="/tmp/t1.jsonl").run(case["borrower"], case["period"])
        b = Monitor(audit_path="/tmp/t2.jsonl").run(case["borrower"], case["period"],
                                                     pkg_dir=DATA / "twins" / case["borrower"] / case["period"])
        if case["case"] == "prompt_injection_text":
            assert a["provisional_status"] == b["provisional_status"]
            assert a["engine"]["lev_ratio"] == b["engine"]["lev_ratio"]
        else:  # injection in a numeric slot: no value guessed, run halts for the analyst
            assert a["provisional_status"] == "HALT" and b["provisional_status"] != "HALT"


def test_memo_guard_blocks_unsupported_number():
    ok = numeric_guard("Leverage 4.35x vs 4.25x", {"4.35", "4.25"})
    bad = numeric_guard("Leverage 4.35x vs 4.25x; borrower expects 4.12x next quarter", {"4.35", "4.25"})
    assert ok["passed"] and not bad["passed"] and bad["unsupported_tokens"] == ["4.12x"]


def test_step_budget_returns_unresolved():
    m = Monitor(audit_path="/tmp/t3.jsonl")
    m.settings["agent"]["step_budget"] = 1
    r = m.run("AIH", "2025-09-30")
    assert any(f["cause"] == "unresolved" for f in r["findings"])


def test_authority_gate(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    m = Monitor(audit_path=tmp_path / "a.jsonl")
    r = m.run("AIH", "2025-09-30")
    gate = ApprovalGate(log)
    with pytest.raises(AuthorityError):          # open findings
        gate.sign(r, "pm1", "portfolio_manager", "BREACH")
    gate.decide_finding(r, 0, "accept", "analyst1", "analyst")
    with pytest.raises(AuthorityError):          # PM cannot declare a breach
        gate.sign(r, "pm1", "portfolio_manager", "BREACH")
    with pytest.raises(AuthorityError):          # override without rationale
        gate.sign(r, "cc1", "credit_committee", "COMPLIANT")
    with pytest.raises(AuthorityError):          # separation of duties
        gate.sign(r, "analyst1", "credit_committee", "BREACH")
    rec = gate.sign(r, "cc1", "credit_committee", "BREACH")
    assert rec["payload"]["determination"] == "BREACH"
    with pytest.raises(AuthorityError):          # analyst cannot accept findings as a different action
        gate.release_halt(r, "analyst1", "analyst", "x")


def test_audit_chain_detects_tampering(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    for i in range(3):
        log.append("x", {"i": i})
    assert log.verify_chain()[0]
    lines = (tmp_path / "a.jsonl").read_text().splitlines()
    lines[1] = lines[1].replace('"i": 1', '"i": 9')
    (tmp_path / "a.jsonl").write_text("\n".join(lines) + "\n")
    assert log.verify_chain() == (False, 1)
