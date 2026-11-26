"""Draft compliance memo. Every number is a slot filled from engine output or a cited page value.

The numeric guard tokenises the final text and blocks the draft if any number does not come from an
allowed source. This applies equally to the template writer and to LLM-drafted prose.
"""
import re

NUM_TOKEN = re.compile(r"(?<![A-Za-z])\$?\(?-?\d[\d,]*(?:\.\d+)?\)?[%xk]?")


def _norm(tok):
    return tok.strip("$()").rstrip("%xk").replace(",", "")


class Slots:
    def __init__(self):
        self.allowed = set()

    def put(self, s):
        for t in NUM_TOKEN.findall(str(s)):
            self.allowed.add(_norm(t))
        return s


def numeric_guard(text, allowed):
    bad = sorted({t for t in NUM_TOKEN.findall(text) if _norm(t) not in allowed})
    return {"passed": not bad, "unsupported_tokens": bad}


def draft(run):
    """run: pipeline record (dict). Returns (memo_text, guard_result)."""
    S = Slots()
    b, p = run["borrower"], run["period"]
    L = [f"DRAFT COVENANT COMPLIANCE MEMO - {S.put(run['borrower_name'])} - Test Period ending {S.put(p)}",
         "Status: DRAFT. Not a determination until signed by the authorised approver.", ""]
    if run["provisional_status"] == "HALT":
        L.append("PROCESSING HALTED - no compliance status has been computed.")
        for r in run["halt_reasons"]:
            L.append(f"  - {S.put(r)}")
        L.append("Required action: portfolio manager to resolve and release; then re-run.")
        text = "\n".join(L)
        return text, numeric_guard(text, S.allowed)
    e, t = run["engine"], run["terms"]
    L.append(f"Provisional engine status: {run['provisional_status']}")
    L.append(f"Governing agreement version(s): {S.put(', '.join(t['versions']))}")
    L.append("")
    L.append(f"{t['lev_label']} (Section {S.put(t['lev_section'])}): {S.put(f'{e['lev_ratio']:.2f}x')} vs maximum "
             f"{S.put(f'{e['lev_threshold']:.2f}x')}; headroom {S.put(f'{e['lev_headroom'] * 100:.1f}%')}")
    L.append(f"{t['cov_label']}: {S.put(f'{e['cov_ratio']:.2f}x')} vs minimum {S.put(f'{e['cov_min']:.2f}x')}")
    L.append(f"Consolidated EBITDA {S.put(f'${e['cons_ebitda']:,.0f}k')} = EBITDA before Adjustments "
             f"{S.put(f'${e['ebitda_pre']:,.0f}k')} + permitted add-backs {S.put(f'${e['addbacks_permitted']:,.0f}k')}")
    for a in e["addbacks"]:
        L.append(f"  - {a['name']}: claimed {S.put(f'${a['claimed']:,.0f}k')}, permitted {S.put(f'${a['permitted']:,.0f}k')} "
                 f"({a['reason'].replace('_', ' ')})")
    L.append(f"Net debt {S.put(f'${e['net_debt']:,.0f}k')} (cash netted {S.put(f'${e['cash_netted']:,.0f}k')})")
    if e["lev_ratio"] > e["lev_threshold"]:
        L.append(f"Sensitivity: Consolidated EBITDA would need to be {S.put(f'${e['ebitda_change_to_threshold']:,.0f}k')} "
                 f"higher, or net debt {S.put(f'${e['debt_change_to_threshold']:,.0f}k')} lower, to comply.")
    else:
        L.append(f"Sensitivity: a {S.put(f'{e['ebitda_cushion_pct'] * 100:.1f}%')} fall in Consolidated EBITDA "
                 f"(about {S.put(f'${-e['ebitda_change_to_threshold']:,.0f}k')}) or "
                 f"{S.put(f'${-e['debt_change_to_threshold']:,.0f}k')} of additional net debt would cause a breach.")
    if run.get("early_warning"):
        L.append("Early-warning flags: " + "; ".join(S.put(x) for x in run["early_warning"]))
    L.append("")
    if run["findings"]:
        L.append("Certificate discrepancies - PROPOSED causes (analyst must accept or reject each):")
        for i, f in enumerate(run["findings"], 1):
            L.append(f"  {S.put(i)}. {f['component']}: {f['cause'].replace('_', ' ')} "
                     f"[{S.put('; '.join(f.get('citations', [])))}]")
    for fl in run["flags"]:
        L.append(f"Verification flag: {S.put(fl)}")
    L.append("")
    L.append("Decisions reserved to named people (not taken by the system): " + ", ".join(run["required_approvals"]))
    text = "\n".join(L)
    return text, numeric_guard(text, S.allowed)
