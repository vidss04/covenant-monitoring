"""Render synthetic credit agreements and amendments as text with page markers.

The language follows the structure of EDGAR Exhibit 10 credit agreements. Boilerplate
sections are included on purpose: they contain distractor numbers (incurrence tests,
incremental facility ratios, ECF sweep levels) that a chunk retriever can confuse with
the maintenance covenant.
"""
from datetime import date

LINES_PER_PAGE = 40


def _d(iso):
    y, m, d = map(int, iso.split("-"))
    return date(y, m, d).strftime("%B %-d, %Y")


def _ratio(x):
    return f"{x:.2f} to 1.00"


def _money(k):  # thousands -> words-ish dollars
    return f"${k * 1000:,.0f}"


def _cap_text(cap, items):
    joined = " and ".join(f"clause ({c})" for c in items)
    if cap["type"] == "pct":
        return (f"provided that the aggregate amount added back pursuant to {joined} for any Test Period "
                f"shall not exceed {cap['value'] * 100:g}% of EBITDA before Adjustments for such Test Period "
                f"(calculated before giving effect to any such add-back)")
    return (f"provided that the aggregate amount added back pursuant to {joined} for any Test Period "
            f"shall not exceed {_money(cap['value'])}")


BOILER_ART2 = [
    ("2.01", "Commitments", "Subject to the terms and conditions set forth herein, each Lender agrees to make Term Loans to the Borrower on the Closing Date in an aggregate principal amount not exceeding its Term Commitment, and Revolving Loans from time to time during the Availability Period. Amounts repaid in respect of Term Loans may not be reborrowed."),
    ("2.08", "Interest", "The Loans comprising each Term SOFR Borrowing shall bear interest at Adjusted Term SOFR for the Interest Period in effect plus the Applicable Rate. The Applicable Rate shall be determined by reference to the leverage-based pricing grid set forth in Schedule 2.08, with step-downs of 25 basis points at each level below 4.00 to 1.00, 3.50 to 1.00 and 3.00 to 1.00."),
    ("2.11", "Mandatory Prepayments", "Within five Business Days after financial statements are delivered for any fiscal year, the Borrower shall prepay Term Loans in an amount equal to 50% of Excess Cash Flow, reduced to 25% if the leverage ratio as of the last day of such fiscal year is less than 3.00 to 1.00 and to 0% if less than 2.50 to 1.00."),
    ("2.20", "Incremental Facilities", "The Borrower may request Incremental Term Loans in an aggregate amount not to exceed the greater of $50,000,000 and 100% of Consolidated EBITDA, plus an unlimited amount so long as, on a pro forma basis, the leverage ratio would not exceed 4.75 to 1.00. This incurrence test is not a maintenance covenant."),
]

BOILER_ART5 = [
    ("5.01", "Financial Statements", "The Borrower shall deliver to the Administrative Agent (a) within 90 days after the end of each fiscal year, audited consolidated financial statements, and (b) within 45 days after the end of each of the first three fiscal quarters, unaudited consolidated financial statements, in each case certified by a Financial Officer as presenting fairly in all material respects the financial condition of the Borrower."),
    ("5.02", "Compliance Certificate", "Concurrently with any delivery of financial statements under Section 5.01, the Borrower shall deliver a certificate of a Financial Officer substantially in the form of Exhibit D (a) certifying that no Default has occurred, and (b) setting forth reasonably detailed calculations demonstrating compliance with the financial covenants, including a reconciliation of each add-back to Consolidated EBITDA."),
    ("5.09", "Information Regarding Collateral", "The Borrower shall furnish to the Administrative Agent prompt written notice of any change in its legal name, jurisdiction of organization or organizational identification number."),
]

BOILER_ART8 = [
    ("8.01", "Events of Default", "Each of the following shall constitute an Event of Default: (a) failure to pay principal when due; (b) failure to pay interest within three Business Days; (c) failure to observe any financial covenant; (d) failure to deliver the Compliance Certificate within five Business Days after it is due."),
    ("8.04", "Right to Cure", "Notwithstanding Section 8.01, in the event the Borrower fails to comply with a financial covenant, the Borrower may within 15 Business Days after the Compliance Certificate is due receive a Specified Equity Contribution, which shall increase Consolidated EBITDA solely for purposes of determining compliance; provided that no more than two such cures may be made in any four consecutive fiscal quarters and no more than five during the term of this Agreement."),
]


def render_base(bid, b):
    lev, cov = b["leverage"], b["coverage"]
    secs = []  # (section_id, heading, text)
    secs.append(("0", "Preamble",
                 f"CREDIT AGREEMENT dated as of {_d(b['agreement_date'])} among {b['name']}, as the Borrower, "
                 f"the Lenders party hereto from time to time, and Northgate Capital Partners LLC, as Administrative Agent. "
                 f"THIS DOCUMENT IS SYNTHETIC AND WAS CREATED FOR AN ACADEMIC PROJECT."))
    # ---- Article I definitions
    items = list(b["addbacks"].keys())
    letters = "abcdefgh"
    clauses = [f"({letters[i]}) {name}" for i, name in enumerate(items)]
    cap_clauses = []
    for gid, cap in b["caps"].items():
        members = [letters[i] for i, n in enumerate(items) if b["addbacks"][n] == gid]
        cap_clauses.append((cap["section"], _cap_text(cap, members)))
    secs.append(("1.01(a)", "Defined Term: EBITDA before Adjustments",
                 "\"EBITDA before Adjustments\" means, for any Test Period, consolidated operating income of the Borrower "
                 "and its Restricted Subsidiaries for such Test Period plus depreciation and amortization expense, in each case "
                 "determined in accordance with GAAP."))
    secs.append(("1.01", "Defined Term: Consolidated EBITDA",
                 "\"Consolidated EBITDA\" means, for any Test Period, EBITDA before Adjustments for such Test Period plus, "
                 "without duplication and to the extent deducted in computing such amount: " + "; ".join(clauses) +
                 ". No other item shall be added back to Consolidated EBITDA except as expressly set forth in this definition."))
    for sec, txt in cap_clauses:
        secs.append((sec, "Defined Term: Consolidated EBITDA (limitation)", txt[0].upper() + txt[1:] + "."))
    debt_term = "Senior Secured Debt" if lev["debt_basis"] == "secured" else "Total Debt"
    if lev["debt_basis"] == "secured":
        secs.append(("1.01(g)", "Defined Term: Senior Secured Debt",
                     "\"Senior Secured Debt\" means the aggregate principal amount of Revolving Loans and Term Loans outstanding, "
                     "and any other Indebtedness secured by a Lien on the Collateral, excluding the Senior Unsecured Notes."))
    else:
        secs.append(("1.01(g)", "Defined Term: Total Debt",
                     "\"Total Debt\" means the aggregate principal amount of all funded Indebtedness of the Borrower and its "
                     "Restricted Subsidiaries, including Revolving Loans, Term Loans and any notes."))
    if lev["cash_cap"] == 0:
        netting = "No cash shall be netted in computing any leverage ratio."
    elif lev["cash_cap"] is None:
        netting = "\"Net Debt\" means Total Debt minus all Unrestricted Cash."
    else:
        netting = (f"\"Net Debt\" means {debt_term} minus Unrestricted Cash; provided that the amount of Unrestricted Cash "
                   f"netted shall not exceed {_money(lev['cash_cap'])}.")
    secs.append(("1.01(h)", "Defined Term: Net Debt", netting))
    num = (f"{debt_term}" if lev["cash_cap"] == 0 else "Net Debt")
    secs.append(("1.01(i)", f"Defined Term: {lev['label']}",
                 f"\"{lev['label']}\" means, as of the last day of any Test Period, the ratio of (a) {num} as of such day to "
                 f"(b) Consolidated EBITDA for such Test Period."))
    if cov["key"] == "fixed_charge_coverage":
        secs.append(("1.01(j)", "Defined Term: Fixed Charge Coverage Ratio",
                     "\"Fixed Charge Coverage Ratio\" means the ratio of (a) Consolidated EBITDA minus Unfinanced Capital "
                     "Expenditures minus cash taxes paid to (b) Consolidated Interest Expense plus scheduled principal payments "
                     "of Indebtedness, in each case for such Test Period."))
    else:
        secs.append(("1.01(j)", "Defined Term: Interest Coverage Ratio",
                     "\"Interest Coverage Ratio\" means the ratio of (a) Consolidated EBITDA to (b) Consolidated Interest "
                     "Expense, in each case for such Test Period."))
    secs.append(("1.01(k)", "Defined Term: Test Period",
                 "\"Test Period\" means, as of any date, the period of four consecutive fiscal quarters then most recently ended."))
    for s in BOILER_ART2:
        secs.append(s)
    for s in BOILER_ART5:
        secs.append(s)
    # ---- Article VII financial covenants
    sched = b["lev_schedule"]
    if len(sched) == 1:
        ltxt = (f"The Borrower shall not permit the {lev['label']} as of the last day of any Test Period to exceed "
                f"{_ratio(sched[0][1])}.")
    else:
        parts = []
        prev = None
        for end, val in sched:
            if end is None:
                parts.append(f"for any Test Period ending after {_d(prev)}, {_ratio(val)}")
            elif prev is None:
                parts.append(f"for any Test Period ending on or before {_d(end)}, {_ratio(val)}")
            else:
                parts.append(f"for any Test Period ending after {_d(prev)} and on or before {_d(end)}, {_ratio(val)}")
            prev = end
        ltxt = (f"The Borrower shall not permit the {lev['label']} as of the last day of any Test Period to exceed the "
                f"ratio set forth below opposite such Test Period: " + "; ".join(parts) + ".")
    secs.append((lev["section"], f"Financial Covenant: {lev['label']}", ltxt))
    secs.append((cov["section"], f"Financial Covenant: {cov['label']}",
                 f"The Borrower shall not permit the {cov['label']} for any Test Period to be less than {_ratio(cov['min'])}."))
    for s in BOILER_ART8:
        secs.append(s)
    return secs


def render_amendment(bid, b, a):
    lev = b["leverage"]
    secs = [("A0", "Preamble",
             f"{a['title'].upper()} TO CREDIT AGREEMENT dated as of {_d(a['execution'])} among {b['name']}, the Lenders "
             f"party hereto and Northgate Capital Partners LLC, as Administrative Agent. SYNTHETIC DOCUMENT.")]
    ch = a["changes"]
    k = 1
    if "lev_threshold" in ch:
        old = b["lev_schedule"][-1][1]
        for prev in b["amendments"]:
            if prev is a:
                break
            if "lev_threshold" in prev["changes"]:
                old = prev["changes"]["lev_threshold"]
        secs.append((f"A2({chr(96 + k)})", f"Amendment to Section {lev['section']}",
                     f"Section {lev['section']} of the Credit Agreement is hereby amended by replacing the reference to "
                     f"\"{_ratio(old)}\" with \"{_ratio(ch['lev_threshold'])}\"."))
        k += 1
    if "add_addback" in ch:
        name, grp = ch["add_addback"]
        secs.append((f"A2({chr(96 + k)})", "Amendment to definition of Consolidated EBITDA",
                     f"The definition of \"Consolidated EBITDA\" in Section 1.01 is hereby amended by adding a new clause "
                     f"permitting the add-back of {name}, which shall be subject to the same limitation as Pro Forma Cost Savings."))
        k += 1
    if "cap_change" in ch:
        grp, cap = ch["cap_change"]
        secs.append((f"A2({chr(96 + k)})", f"Amendment to Section {cap['section']}",
                     f"Section {cap['section']} of the Credit Agreement is hereby amended and restated so that the aggregate "
                     f"amount of Pro Forma Cost Savings and Run-Rate Synergies added back for any Test Period shall not exceed "
                     f"{cap['value'] * 100:g}% of EBITDA before Adjustments for such Test Period."))
        k += 1
    if a["effective"]:
        eff = (f"This Amendment shall become effective as of {_d(a['effective'])} (the \"Amendment Effective Date\") and the "
               f"amendments in Section 2 shall apply to each Test Period ending on or after the Amendment Effective Date.")
    else:
        eff = (f"This Amendment shall become effective on {a['effective_text']} (the \"Amendment Effective Date\"), and the "
               f"amendments in Section 2 shall apply to each Test Period ending on or after the Amendment Effective Date.")
    secs.append(("A3", "Conditions to Effectiveness", eff))
    secs.append(("A4", "Fees", "The Borrower shall pay to each consenting Lender an amendment fee equal to 0.25% of such "
                               "Lender's Commitments. Except as expressly amended hereby, the Credit Agreement remains in full force."))
    return secs


def paginate(secs, doc_id):
    """Turn sections into text with [[PAGE n]] markers. Returns (text, {section: page})."""
    import textwrap
    lines, sec_page = [], {}
    page = 1
    lines.append(f"[[PAGE {page}]]")
    count = 0
    for sid, head, body in secs:
        block = [f"Section {sid}. {head}."] + textwrap.wrap(body, 95) + [""]
        if count + len(block) > LINES_PER_PAGE:
            page += 1
            lines.append(f"[[PAGE {page}]]")
            count = 0
        sec_page[sid] = page
        lines.extend(block)
        count += len(block)
    return "\n".join(lines), sec_page
