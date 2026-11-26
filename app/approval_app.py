"""Analyst / approver screen.  Run:  streamlit run app/approval_app.py

This is the only place borrower free text and page images are shown - to a person. Every decision
goes through cov.approval.ApprovalGate, which enforces the delegation-of-authority matrix and writes
to the same append-only audit log as the pipeline.
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from cov.approval import ApprovalGate, AuthorityError
from cov.audit import AuditLog
from cov.common import DATA, RESULTS
from cov.pipeline import Monitor

st.set_page_config(page_title="Covenant Monitoring - Approval", layout="wide")
AUDIT = RESULTS / "demo_audit_log.jsonl"


@st.cache_resource
def monitor():
    return Monitor(audit_path=AUDIT)


def page_image(pdf, page):
    import pymupdf
    with pymupdf.open(pdf) as d:
        return d[page - 1].get_pixmap(dpi=110).tobytes("png")


log = AuditLog(AUDIT)
gate = ApprovalGate(log)
st.sidebar.title("Signed-in user")
user = st.sidebar.text_input("User id", "analyst.jane")
role = st.sidebar.selectbox("Role", ["analyst", "portfolio_manager", "credit_committee"])
st.sidebar.caption("Roles map to config/settings.json -> authority. The system itself holds no role.")
borrowers = sorted(p.name for p in (DATA / "borrowers").iterdir())
b = st.sidebar.selectbox("Borrower", borrowers)
periods = sorted(p.name for p in (DATA / "borrowers" / b / "packages").iterdir())
p = st.sidebar.selectbox("Test period", periods, index=len(periods) - 1)

if st.sidebar.button("Run monitoring cycle for this borrower"):
    m = monitor()
    m.prior.pop(b, None), m.history.pop(b, None)
    for q in periods:
        m.run(b, q)

runs = [e["payload"] for e in log.entries() if e["kind"] == "run" and e["payload"]["borrower"] == b]
run = next((r for r in reversed(runs) if r["period"] == p), None)
st.title(f"{b} - test period ending {p}")
if not run:
    st.info("No run yet. Use 'Run monitoring cycle' in the sidebar.")
    st.stop()

status = run["provisional_status"]
color = {"COMPLIANT": "green", "TIGHT": "orange", "BREACH": "red", "HALT": "gray"}[status]
st.markdown(f"### Provisional engine status: :{color}[**{status}**]  \n"
            f"Run `{run['run_id'][:8]}` | engine {run['engine_version']} | code {run['code_commit']} | "
            f"extractor `{run['extractor']}` | investigator `{run['investigator']}`")
if run["halt_reasons"]:
    st.error("Processing halted - no status computed:\n\n" + "\n".join(f"- {h}" for h in run["halt_reasons"]))

c1, c2 = st.columns([3, 2])
with c1:
    if run.get("engine"):
        e = run["engine"]
        st.subheader("Engine output (deterministic)")
        st.table(pd.DataFrame({
            "Metric": [run["terms"]["lev_label"], "Threshold (governing)", "Headroom", run["terms"]["cov_label"],
                       "Consolidated EBITDA ($k)", "Net debt ($k)"],
            "Value": [f"{e['lev_ratio']:.3f}x", f"{e['lev_threshold']:.2f}x ({', '.join(run['terms']['versions'])})",
                      f"{e['lev_headroom']:.1%}", f"{e['cov_ratio']:.2f}x (min {e['cov_min']:.2f}x)",
                      f"{e['cons_ebitda']:,.0f}", f"{e['net_debt']:,.0f}"]}))
        st.caption(" | ".join(e["trace"]))
        st.dataframe(pd.DataFrame(e["addbacks"]), hide_index=True)
        hist = [(r["period"], r["engine"]["lev_headroom"] * 100) for r in runs if r.get("engine")]
        if hist:
            st.line_chart(pd.DataFrame(hist, columns=["period", "headroom %"]).set_index("period"))
        if run.get("early_warning"):
            st.warning("Early warning: " + "; ".join(run["early_warning"]))
    if run.get("components"):
        st.subheader("Certificate vs engine")
        st.dataframe(pd.DataFrame(run["components"]), hide_index=True)
    for fl in run["flags"]:
        st.warning(fl)
with c2:
    st.subheader("Governing terms (resolved by effective date)")
    for r in run["terms"]["reasons"]:
        st.write("- " + r)
    st.json(run["terms"]["evidence"], expanded=False)
    if run["free_text_for_analyst"]:
        st.subheader("Borrower free text (shown to you only - never to the engine or agent)")
        for t in run["free_text_for_analyst"]:
            st.error(f"[{t['doc']} p{t['page']}] {t['flag']}: {t['text']}")

pkg = DATA / "borrowers" / b / "packages" / p
st.subheader("Proposed findings - accept or reject each")
for i, f in enumerate(run["findings"]):
    with st.expander(f"{i + 1}. {f['component']} -> {f['cause']}  (source: {f.get('source')})", expanded=True):
        st.write(f.get("explanation", ""))
        st.write("Citations: " + "; ".join(f.get("citations", [])))
        cites = [c for c in f.get("citations", []) if c.startswith(("certificate:p", "financials:p"))]
        if cites:
            doc, pg = cites[0].split(":p")
            st.image(page_image(pkg / f"{doc}.pdf", int(pg.split()[0])), caption=cites[0], width=520)
        a, r_ = st.columns(2)
        if a.button("Accept", key=f"a{i}"):
            try:
                gate.decide_finding(run, i, "accept", user, role); st.success("recorded")
            except AuthorityError as ex:
                st.error(str(ex))
        if r_.button("Reject", key=f"r{i}"):
            try:
                gate.decide_finding(run, i, "reject", user, role); st.success("recorded")
            except AuthorityError as ex:
                st.error(str(ex))
for fld in run.get("pending_value_acceptance", []):
    if st.button(f"Accept re-extracted value for {fld}", key=f"v{fld}"):
        try:
            gate.accept_value(run, fld, "pagewise_pass2", user, role); st.success("recorded")
        except AuthorityError as ex:
            st.error(str(ex))

st.subheader("Draft memo")
st.code(run["memo"], language=None)
st.caption(f"Numeric guard: {'passed' if run['memo_guard']['passed'] else 'BLOCKED ' + str(run['memo_guard']['unsupported_tokens'])}")
det = st.selectbox("Determination", ["COMPLIANT", "TIGHT", "BREACH"],
                   index=["COMPLIANT", "TIGHT", "BREACH"].index(status) if status != "HALT" else 0)
note = st.text_input("Rationale (required if different from engine status)")
if st.button("Sign determination"):
    try:
        gate.sign(run, user, role, det, note); st.success("Determination recorded in the audit log")
    except AuthorityError as ex:
        st.error(str(ex))
with st.expander("Audit trail for this run"):
    st.json([e for e in log.entries() if e["payload"].get("run_id") == run["run_id"]], expanded=False)
