"""Deterministic covenant engine. No model output ever reaches these functions as a number;
inputs are accepted, page-tied figures and the resolved Terms. One function per covenant kind.
"""
from dataclasses import asdict, dataclass, field
from typing import Optional

from cov.kg import Terms

ENGINE_VERSION = "1.0.0"


@dataclass
class AddbackLine:
    name: str
    claimed: float
    permitted: float
    cap_id: Optional[str]
    reason: str          # ok | not_permitted | group_over_cap | uncapped


@dataclass
class EngineResult:
    period: str
    ebitda_pre: float
    addbacks: list
    addbacks_permitted: float
    cons_ebitda: float
    debt_basis_amount: float
    cash_netted: float
    net_debt: float
    lev_ratio: float
    lev_threshold: float
    lev_headroom: float
    cov_ratio: float
    cov_min: float
    cov_headroom: float
    status: str
    ebitda_change_to_threshold: float   # + : EBITDA must rise by this to comply; - : cushion before breach
    debt_change_to_threshold: float     # + : debt must fall by this to comply; - : debt room before breach
    ebitda_cushion_pct: float           # % fall in Consolidated EBITDA that would trigger a leverage breach
    trace: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def apply_addbacks(terms: Terms, claims: dict, ebitda_pre: float):
    lines, groups = [], {}
    for name, amt in claims.items():
        if name not in terms.addbacks:
            lines.append(AddbackLine(name, amt, 0.0, None, "not_permitted"))
            continue
        cid = terms.addbacks[name]
        ln = AddbackLine(name, amt, amt, cid, "uncapped" if cid is None else "ok")
        lines.append(ln)
        if cid:
            groups.setdefault(cid, []).append(ln)
    for cid, members in groups.items():
        cap = terms.caps[cid]
        limit = cap["value"] * ebitda_pre if cap["cap_type"] == "pct" else cap["value"]
        total = sum(m.claimed for m in members)
        if total > limit + 1e-9:
            excess = total - limit
            for m in reversed(members):  # cut from the last item in the group
                cut = min(excess, m.permitted)
                m.permitted -= cut
                excess -= cut
            for m in members:
                m.reason = "group_over_cap"
    return lines, sum(l.permitted for l in lines)


def leverage(terms: Terms, debt_basis_amount: float, cash: float, cons: float):
    if terms.cash_cap == 0:
        netted = 0.0
    elif terms.cash_cap is None:
        netted = cash
    else:
        netted = min(cash, terms.cash_cap)
    net = debt_basis_amount - netted
    return net, netted, net / cons


def interest_coverage(cons, interest):
    return cons / interest


def fixed_charge_coverage(cons, capex, taxes, interest, principal):
    return (cons - capex - taxes) / (interest + principal)


def run(terms: Terms, figs: dict, claims: dict, tight_headroom: float = 0.10) -> EngineResult:
    """figs: ebitda_pre, debt_basis_amount, cash, interest, capex, cash_taxes, principal (USD thousands)."""
    tr = []
    lines, permitted = apply_addbacks(terms, claims, figs["ebitda_pre"])
    cons = figs["ebitda_pre"] + permitted
    tr.append(f"Consolidated EBITDA = EBITDA before Adjustments {figs['ebitda_pre']:,.0f} + permitted add-backs "
              f"{permitted:,.0f} = {cons:,.0f}")
    net, netted, lev = leverage(terms, figs["debt_basis_amount"], figs["cash"], cons)
    tr.append(f"{terms.lev_label} = ({figs['debt_basis_amount']:,.0f} - cash netted {netted:,.0f}) / {cons:,.0f} = {lev:.4f}x")
    if terms.cov_kind == "fcc":
        cov = fixed_charge_coverage(cons, figs["capex"], figs["cash_taxes"], figs["interest"], figs["principal"])
        tr.append(f"FCCR = ({cons:,.0f} - {figs['capex']:,.0f} - {figs['cash_taxes']:,.0f}) / "
                  f"({figs['interest']:,.0f} + {figs['principal']:,.0f}) = {cov:.4f}x")
    else:
        cov = interest_coverage(cons, figs["interest"])
        tr.append(f"ICR = {cons:,.0f} / {figs['interest']:,.0f} = {cov:.4f}x")
    thr, cmin = terms.lev_threshold, terms.cov_min
    lev_head = (thr - lev) / thr
    cov_head = (cov - cmin) / cmin
    if lev > thr or cov < cmin:
        status = "BREACH"
    elif min(lev_head, cov_head) < tight_headroom:
        status = "TIGHT"
    else:
        status = "COMPLIANT"
    ebitda_chg = net / thr - cons
    debt_chg = net - thr * cons
    cushion = 1 - (net / thr) / cons
    tr.append(f"threshold {thr:.2f}x -> headroom {lev_head:.1%}; status {status}")
    return EngineResult(terms.period, figs["ebitda_pre"], [asdict(l) for l in lines], permitted, cons,
                        figs["debt_basis_amount"], netted, net, lev, thr, lev_head, cov, cmin, cov_head, status,
                        ebitda_chg, debt_chg, cushion, tr)


def early_warning(history: list, settings: dict):
    """history: list of (period, lev_headroom). Flags declines on reported figures only (no forecasting)."""
    flags = []
    if not history:
        return flags
    n = settings["early_warning"]["consecutive_declines"]
    floor = settings["early_warning"]["headroom_floor"]
    heads = [h for _, h in history]
    if len(heads) > n and all(heads[-i] < heads[-i - 1] for i in range(1, n + 1)):
        flags.append(f"headroom declined {n} consecutive test periods ({heads[-n - 1]:.1%} -> {heads[-1]:.1%})")
    if heads[-1] < floor:
        flags.append(f"headroom {heads[-1]:.1%} below watch floor {floor:.0%}")
    return flags
