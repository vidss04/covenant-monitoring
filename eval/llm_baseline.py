"""Baseline B3 (proposal section 6): a single prompt asks an LLM to judge compliance directly from
the agreement text and the certificate text. Requires ANTHROPIC_API_KEY.

    ANTHROPIC_API_KEY=... python -m eval.llm_baseline           # writes results/llm_baseline.json

Also runs the full pipeline with the Claude investigator (same tools as the rule investigator) so the
two agent policies can be compared on identical inputs.
"""
import json
import sys
import warnings

warnings.filterwarnings("ignore")

from cov import llm
from cov.agent_llm import ClaudeInvestigator
from cov.common import DATA, RESULTS
from cov.extract import pdf_pages_plumber
from cov.pipeline import Monitor

KEY = json.loads((DATA / "gold" / "answer_key.json").read_text())

SCHEMA = {"type": "object", "properties": {
    "status": {"type": "string", "enum": ["COMPLIANT", "TIGHT", "BREACH", "CANNOT_DETERMINE"]},
    "leverage_ratio": {"type": "number"}, "governing_threshold": {"type": "number"},
    "explanation": {"type": "string"}}, "required": ["status", "leverage_ratio", "governing_threshold"]}


def single_prompt(row):
    adir = DATA / "borrowers" / row["borrower"] / "agreement"
    agreement = "\n\n".join(f"=== {f.stem} ===\n{f.read_text()}" for f in sorted(adir.glob("*.txt")))
    pkg = DATA / "borrowers" / row["borrower"] / "packages" / row["period"]
    cert = "\n".join(pdf_pages_plumber(pkg / "certificate.pdf"))
    fin = "\n".join(pdf_pages_plumber(pkg / "financials.pdf"))
    user = (f"Credit agreement and amendments:\n{agreement}\n\nFinancial statements:\n{fin}\n\nCompliance certificate:\n{cert}\n\n"
            f"Determine whether the borrower complies with its leverage covenant for the Test Period ending {row['period']}. "
            f"TIGHT means compliant with headroom under 10% of the threshold.")
    return llm.forced_tool("baseline_single_prompt", "You are a credit analyst.", user, "answer", SCHEMA)


def _save(path, obj):
    path.write_text(json.dumps(obj, indent=1, default=str))


def main():
    if not llm.available():
        sys.exit("Set ANTHROPIC_API_KEY to run the LLM baselines.")
    RESULTS.mkdir(exist_ok=True)
    out_path = RESULTS / "llm_baseline.json"
    state = json.loads(out_path.read_text()) if out_path.exists() else {}
    # rows that errored are dropped so a rerun retries them
    state["single_prompt"] = [r for r in state.get("single_prompt", []) if r.get("llm_status") != "ERROR"]
    state["claude_agent"] = [r for r in state.get("claude_agent", []) if r.get("status") != "ERROR"]
    done_sp = {(r["borrower"], r["period"]) for r in state["single_prompt"]}
    done_ag = {(r["borrower"], r["period"]) for r in state["claude_agent"]}
    try:  # fail fast on a bad key instead of recording 64 errors
        llm.call("auth_check", messages=[{"role": "user", "content": "Reply OK."}], max_tokens=5)
    except Exception as e:  # noqa
        sys.exit(f"API check failed: {type(e).__name__}: {e}\nFix ANTHROPIC_API_KEY (see README) and rerun; nothing was overwritten.")
    state.setdefault("single_prompt", [])
    state.setdefault("claude_agent", [])
    only = sys.argv[1] if len(sys.argv) > 1 else "both"   # both | single | agent
    if only in ("both", "single"):
        for row in KEY:
            if (row["borrower"], row["period"]) in done_sp:
                continue
            try:
                a = single_prompt(row)
            except Exception as e:  # noqa
                a = {"status": "ERROR", "explanation": f"{type(e).__name__}: {e}"}
            state["single_prompt"].append({"borrower": row["borrower"], "period": row["period"], "case": row["case"],
                                           "expected": row["expected_status"], "llm_status": a.get("status"),
                                           "llm_ratio": a.get("leverage_ratio"), "true_ratio": row["lev_ratio"],
                                           "llm_threshold": a.get("governing_threshold"),
                                           "true_threshold": row["lev_threshold"], "explanation": a.get("explanation")})
            state["usage"] = llm.USAGE
            _save(out_path, state)   # saved after every call: a crash loses nothing
            r = state["single_prompt"][-1]
            print(f"[single] {r['borrower']} {r['period']} expected={r['expected']} llm={r['llm_status']}", flush=True)
    if only in ("both", "agent"):
        m = Monitor(audit_path=RESULTS / "audit_log_claude_agent.jsonl", investigator=ClaudeInvestigator())
        for row in KEY:  # all periods run so prior-package checks work; only new ones are recorded
            try:
                r = m.run(row["borrower"], row["period"])
            except Exception as e:  # noqa
                r = {"findings": [{"cause": f"ERROR {type(e).__name__}: {e}"}], "provisional_status": "ERROR"}
            if (row["borrower"], row["period"]) in done_ag:
                continue
            state["claude_agent"].append({"borrower": row["borrower"], "period": row["period"],
                                          "expected_cause": row["expected_cause"],
                                          "proposed": sorted({f["cause"] for f in r["findings"]}),
                                          "steps": r.get("agent_steps"), "status": r["provisional_status"],
                                          "trace": r.get("agent_trace")})
            state["usage"] = llm.USAGE
            _save(out_path, state)
            a = state["claude_agent"][-1]
            print(f"[agent] {a['borrower']} {a['period']} expected={a['expected_cause']} proposed={a['proposed']}", flush=True)
    print("saved", out_path)


if __name__ == "__main__":
    main()
