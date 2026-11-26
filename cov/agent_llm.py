"""Claude-driven ReAct policy over the same read-only Toolbox as RuleInvestigator.

The model sees only what the tools return (typed numbers, enums, citations). It never receives
clause text or certificate text, and the tool layer has no write operations.
"""
import json

from cov import llm
from cov.agent import CAUSES, TOOL_SPECS, BudgetExceeded

SYSTEM = (
    "You investigate why a lender's covenant calculation differs from a borrower's compliance certificate. "
    "Use the tools to find the cause of each discrepancy. You cannot change any figure or decide compliance; "
    "you only propose causes from this closed set: " + ", ".join(CAUSES) + ". "
    "Cite pages/sections returned by tools. If you cannot explain a gap, use 'unresolved'. "
    "Call submit_findings exactly once when done."
)


class ClaudeInvestigator:
    name = "claude"

    def investigate(self, tb):
        msgs = [{"role": "user", "content": "Investigate the discrepancies for this test period. Start with list_discrepancies."}]
        try:
            while True:
                resp = llm.call("agent", system=SYSTEM, tools=TOOL_SPECS, messages=msgs)
                msgs.append({"role": "assistant", "content": resp.content})
                uses = [b for b in resp.content if b.type == "tool_use"]
                if not uses:
                    return [{"component": "*", "cause": "unresolved", "citations": [],
                             "explanation": "agent stopped without submitting findings"}]
                results = []
                for u in uses:
                    if u.name == "submit_findings":
                        out = []
                        for f in u.input.get("findings", []):
                            if f.get("cause") not in CAUSES:  # closed set enforced in code
                                f = {**f, "cause": "unresolved", "explanation": f"invalid cause {f.get('cause')!r}"}
                            out.append(f)
                        tb.trace.append({"step": len(tb.trace) + 1, "tool": "submit_findings", "args": u.input})
                        return out
                    fn = getattr(tb, u.name, None)
                    if fn is None or u.name.startswith("_"):
                        res = {"error": "unknown tool"}
                    else:
                        res = fn(**u.input)
                    results.append({"type": "tool_result", "tool_use_id": u.id, "content": json.dumps(res, default=str)})
                msgs.append({"role": "user", "content": results})
        except BudgetExceeded:
            return [{"component": "*", "cause": "unresolved", "citations": [],
                     "explanation": f"step budget of {tb.budget} exhausted"}]
