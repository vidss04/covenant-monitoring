"""Verification rules. Independent evidence sources (XBRL, the borrower's own statements, prior
packages, the resolved agreement terms) - never another LLM.
"""
import json
from datetime import date

from cov.common import DATA, Extraction

XBRL_TAGS = {"revenue": "Revenues", "operating_income": "OperatingIncomeLoss",
             "da": "DepreciationDepletionAndAmortization", "interest_expense": "InterestExpense",
             "total_debt": "LongTermDebt", "cash": "CashAndCashEquivalentsAtCarryingValue"}


def load_xbrl(borrower):
    return json.loads((DATA / "borrowers" / borrower / "xbrl_companyfacts.json").read_text())


def xbrl_value(facts, tag, period):
    for f in facts["facts"]["us-gaap"].get(tag, {}).get("units", {}).get("USD", []):
        if f["end"] == period and f.get("filed_for", period) == period:  # as originally filed for the period
            return f["val"] / 1000.0
    return None


def xbrl_tieout(ex: Extraction, facts, period, pct):
    """Tie current-period GAAP line items to XBRL. Marks each field's verification status."""
    results = {}
    for key, tag in XBRL_TAGS.items():
        fname = key if key in ("total_debt", "cash") else f"{key}_{period}"
        f = ex.fields.get(fname)
        ref = xbrl_value(facts, tag, period)
        if f is None or ref is None:
            continue
        ok = f.value is not None and abs(f.value - ref) <= pct * max(abs(ref), 1)
        f.verification = "xbrl_tied" if ok else "xbrl_failed"
        results[fname] = {"extracted": f.value, "xbrl": ref, "tied": ok, "page": f.page}
    return results


def tol(settings, ref):
    t = settings["tolerance"]
    return max(t["component_pct"] * abs(ref), t["component_abs_thousands"])


def certificate_components(ex: Extraction, eng, figs, settings):
    """Engine vs certificate, component by component. Numbers and citations only."""
    out = []

    def add(name, engine_val, cert_key):
        f = ex.fields.get(cert_key)
        if f is None or f.value is None:
            return
        diff = f.value - engine_val
        out.append({"component": name, "engine": round(engine_val, 4), "certificate": f.value,
                    "diff": round(diff, 4), "exceeds_tolerance": abs(diff) > tol(settings, engine_val),
                    "cert_page": f.page})

    add("ebitda_pre", eng.ebitda_pre, "cert.ebitda_pre")
    for ln in eng.addbacks:
        f = ex.fields.get(f"cert.addback::{ln['name']}")
        if f is not None and f.value is not None:
            diff = f.value - ln["permitted"]
            out.append({"component": f"addback::{ln['name']}", "engine": ln["permitted"], "certificate": f.value,
                        "diff": diff, "exceeds_tolerance": abs(diff) > tol(settings, max(ln["permitted"], 1)),
                        "cert_page": f.page, "engine_reason": ln["reason"]})
    add("cons_ebitda", eng.cons_ebitda, "cert.cons_ebitda")
    add("debt", eng.debt_basis_amount, "cert.debt")
    add("interest", figs["interest"], "cert.interest")
    lr = ex.fields.get("cert.lev_ratio")
    ratio_gap = None
    if lr and lr.value is not None:
        ratio_gap = lr.value - eng.lev_ratio
        out.append({"component": "lev_ratio", "engine": round(eng.lev_ratio, 4), "certificate": lr.value,
                    "diff": round(ratio_gap, 4), "exceeds_tolerance": abs(ratio_gap) > settings["tolerance"]["ratio_abs"],
                    "cert_page": lr.page})
    return out


def threshold_check(ex: Extraction, terms):
    f = ex.fields.get("cert.lev_required")
    if f is None or f.value is None or terms.lev_threshold is None:
        return None
    if abs(f.value - terms.lev_threshold) > 1e-9:
        return {"rule": "threshold_mismatch", "certificate_threshold": f.value, "governing_threshold": terms.lev_threshold,
                "cert_page": f.page, "governing_evidence": terms.evidence.get("lev_threshold"),
                "versions": terms.versions}
    return None


def period_consistency(ex: Extraction, prior: Extraction, quarters):
    """Compare overlapping quarters with the previous package. A change means a restatement."""
    if prior is None:
        return []
    diffs = []
    for q in quarters:
        for k in ("operating_income", "da", "interest_expense", "revenue"):
            a, b = ex.fields.get(f"{k}_{q}"), prior.fields.get(f"{k}_{q}")
            if a and b and a.value is not None and b.value is not None and abs(a.value - b.value) > 0.5:
                diffs.append({"quarter": q, "line": k, "current_package": a.value, "prior_package": b.value,
                              "delta": a.value - b.value, "current_page": a.page, "prior_period": prior.period})
    return diffs


def certificate_arithmetic(ex: Extraction):
    pre = ex.get("cert.ebitda_pre")
    cons = ex.get("cert.cons_ebitda")
    adds = [f.value for k, f in ex.fields.items() if k.startswith("cert.addback::") and f.value is not None]
    if pre is None or cons is None:
        return None
    s = pre + sum(adds)
    return {"stated_cons_ebitda": cons, "sum_of_components": s, "diff": cons - s}


def statement_vs_certificate(ex: Extraction, figs):
    out = {}
    for comp, cert_key, stmt in (("debt", "cert.debt", figs["debt_basis_amount"]),
                                 ("interest", "cert.interest", figs["interest"]),
                                 ("ebitda_pre", "cert.ebitda_pre", figs["ebitda_pre"])):
        f = ex.fields.get(cert_key)
        if f is not None and f.value is not None:
            out[comp] = {"statement": stmt, "certificate": f.value, "diff": f.value - stmt, "cert_page": f.page}
    return out


def delivery_check(period, received: str = None, days=45):
    """Reporting deadline (Section 5.01/5.02): 45 days after quarter end. Deterministic."""
    y, m, d = map(int, period.split("-"))
    due = date.fromordinal(date(y, m, d).toordinal() + days).isoformat()
    received = received or due
    return {"due": due, "received": received, "late": received > due}
