"""Scripted live demo (terminal). Mirrors docs/demo_script.md.

    python demo.py            # walk through the four demo scenes
"""
import json
import warnings

warnings.filterwarnings("ignore")

from cov.approval import ApprovalGate, AuthorityError
from cov.common import DATA, RESULTS
from cov.pipeline import Monitor

LOG = RESULTS / "demo_cli_audit.jsonl"
LOG.unlink(missing_ok=True)
m = Monitor(audit_path=LOG)
gate = ApprovalGate(m.audit)


def scene(title):
    print("\n" + "=" * 100 + f"\n{title}\n" + "=" * 100)


for p in ("2024-12-31", "2025-03-31", "2025-06-30"):
    m.run("AIH", p)

scene("SCENE 1 - Apex Q3 2025: certificate says 4.08x vs 4.50x 'compliant'. Amendment No.1 changed the test.")
r = m.run("AIH", "2025-09-30")
print(r["memo"])
print("\nAgent trace (typed tool calls only):")
for t in r["agent_trace"]:
    print(f"  step {t['step']}: {t['tool']}({t['args']}) -> {json.dumps(t['result'], default=str)[:110]}")

scene("SCENE 2 - Authority: who may do what")
for who, role, action in (("cc.chair", "credit_committee", "sign BREACH"), ("analyst.jane", "analyst", "accept finding"),
                          ("pm.raj", "portfolio_manager", "sign BREACH"),
                          ("analyst.jane", "credit_committee", "sign BREACH (same person)"),
                          ("cc.chair", "credit_committee", "sign BREACH ")):
    try:
        if action == "accept finding":
            gate.decide_finding(r, 0, "accept", who, role)
        else:
            gate.sign(r, who, role, "BREACH")
        print(f"  OK      {who:14s} {role:18s} {action}")
    except AuthorityError as e:
        print(f"  REFUSED {who:14s} {role:18s} {action}: {e}")

scene("SCENE 3 - Apex Q4 2025: the certificate tells 'automated review systems' to report COMPLIANT")
r = m.run("AIH", "2025-12-31")
print("Free text routed to analyst only:", r["free_text_for_analyst"][0]["text"][:120], "...")
print("Status:", r["provisional_status"], f"| leverage {r['engine']['lev_ratio']:.2f}x vs {r['engine']['lev_threshold']:.2f}x")
twin = Monitor(audit_path=RESULTS / "scratch.jsonl").run("AIH", "2025-12-31", pkg_dir=DATA / "twins/AIH/2025-12-31")
print("Clean twin (same numbers, no instruction):", twin["provisional_status"], f"{twin['engine']['lev_ratio']:.2f}x")
(RESULTS / "scratch.jsonl").unlink(missing_ok=True)

scene("SCENE 4 - Cedar Q2 2026: amendment with no calendar effective date -> the system stops")
for p in ("2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"):
    m.run("CLC", p)
r = m.run("CLC", "2026-06-30")
print(r["memo"])
print("\nAudit chain valid:", m.audit.verify_chain()[0], f"({len(m.audit.entries())} entries in {LOG.name})")
