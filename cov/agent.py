"""Discrepancy investigation: a bounded ReAct-style loop over READ-ONLY tools.

Authority boundary (enforced by construction, not by prompt):
  * Tools return typed numbers, enums and citations. No clause text or certificate text is ever
    returned, so instructions embedded in borrower documents cannot reach the agent.
  * No tool can change a figure, accept an add-back, or set a status. The only output is a list of
    proposed findings from a closed set of causes, each with citations, for an analyst to accept or reject.
  * Step budget (config) caps tool calls; an unexplained gap is returned as `unresolved`.

Two interchangeable policies drive the same tool interface:
  * RuleInvestigator   - deterministic policy (offline default, fully reproducible)
  * ClaudeInvestigator - LLM ReAct policy (agent_llm.py), used when ANTHROPIC_API_KEY is set
"""
import json

from cov import verify

CAUSES = ["borrower_arithmetic_error", "addback_over_cap", "addback_not_permitted", "period_restatement_mismatch",
          "statement_certificate_mismatch", "extraction_error_suspected", "unresolved"]


class BudgetExceeded(Exception):
    pass


class Toolbox:
    """Read-only views over one run's typed state."""

    def __init__(self, ctx, budget):
        self.ctx, self.budget, self.trace = ctx, budget, []

    def _log(self, tool, args, result):
        if len(self.trace) >= self.budget:
            raise BudgetExceeded()
        self.trace.append({"step": len(self.trace) + 1, "tool": tool, "args": args, "result": result})
        return result

    # ---------------------------------------------------------------- tools
    def list_discrepancies(self):
        comps = [c for c in self.ctx["components"] if c["exceeds_tolerance"]]
        return self._log("list_discrepancies", {}, comps)

    def get_addback_terms(self, name):
        t = self.ctx["terms"]
        cid = t.addbacks.get(name, "__absent__")
        res = {"addback": name, "permitted_by_governing_definition": cid != "__absent__",
               "governing_versions": t.versions,
               "cap": (t.caps[cid] if cid not in (None, "__absent__") else None),
               "evidence": t.evidence.get("addbacks", [])}
        return self._log("get_addback_terms", {"name": name}, res)

    def check_cap(self, name):
        ln = next((l for l in self.ctx["engine"].addbacks if l["name"] == name), None)
        return self._log("check_cap", {"name": name}, ln)

    def check_certificate_arithmetic(self):
        return self._log("check_certificate_arithmetic", {}, verify.certificate_arithmetic(self.ctx["extraction"]))

    def check_period_consistency(self):
        return self._log("check_period_consistency", {}, self.ctx["period_diffs"])

    def compare_statement_to_certificate(self, component):
        return self._log("compare_statement_to_certificate", {"component": component},
                         self.ctx["stmt_vs_cert"].get(component))

    def xbrl_tieout(self, field):
        return self._log("xbrl_tieout", {"field": field}, self.ctx["xbrl"].get(field))

    def request_reextraction(self, field):
        """Asks the second, independent extractor to re-read one field. Read-only: the result is
        shown to the analyst; it does not replace any figure."""
        res = self.ctx["reextract"](field)
        return self._log("request_reextraction", {"field": field}, res)

    def describe(self):
        return TOOL_SPECS


TOOL_SPECS = [
    {"name": "list_discrepancies", "description": "Components where engine and certificate differ beyond tolerance.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_addback_terms", "description": "Governing definition status and cap for one add-back (citations only).",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "check_cap", "description": "Engine's claimed vs permitted amount for one add-back.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "check_certificate_arithmetic", "description": "Does the certificate's Consolidated EBITDA equal the sum of its own components?",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "check_period_consistency", "description": "Quarterly figures that changed versus the prior package.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "compare_statement_to_certificate", "description": "Statement value vs certificate value for debt, interest or ebitda_pre.",
     "input_schema": {"type": "object", "properties": {"component": {"type": "string", "enum": ["debt", "interest", "ebitda_pre"]}},
                      "required": ["component"]}},
    {"name": "xbrl_tieout", "description": "XBRL tie-out result for a GAAP field (e.g. total_debt, cash).",
     "input_schema": {"type": "object", "properties": {"field": {"type": "string"}}, "required": ["field"]}},
    {"name": "request_reextraction", "description": "Independent second read of one extracted field.",
     "input_schema": {"type": "object", "properties": {"field": {"type": "string"}}, "required": ["field"]}},
    {"name": "submit_findings", "description": "Final answer. Closed-set causes with citations. Ends the investigation.",
     "input_schema": {"type": "object", "properties": {"findings": {"type": "array", "items": {"type": "object", "properties": {
         "component": {"type": "string"}, "cause": {"type": "string", "enum": CAUSES},
         "explanation": {"type": "string"}, "citations": {"type": "array", "items": {"type": "string"}}},
         "required": ["component", "cause"]}}}, "required": ["findings"]}},
]


class RuleInvestigator:
    name = "rule"

    def investigate(self, tb: Toolbox):
        findings, explained = [], set()
        try:
            gaps = tb.list_discrepancies()
            comps = {g["component"]: g for g in gaps}
            # 1. add-backs the engine cut or excluded
            for comp, g in comps.items():
                if not comp.startswith("addback::"):
                    continue
                name = comp.split("::", 1)[1]
                terms = tb.get_addback_terms(name)
                line = tb.check_cap(name)
                if not terms["permitted_by_governing_definition"]:
                    cause = "addback_not_permitted"
                    cite = [f"{d}:{s}:p{p}" for d, s, p in terms["evidence"][:1]] + [f"certificate:p{g['cert_page']}"]
                elif line and line["reason"] == "group_over_cap":
                    cause = "addback_over_cap"
                    cap = terms["cap"]
                    cite = [f"{cap['doc']}:{cap['section']}", f"certificate:p{g['cert_page']}"]
                else:
                    continue
                findings.append({"component": comp, "cause": cause, "citations": cite,
                                 "explanation": f"claimed {g['certificate']:,.0f}, permitted {g['engine']:,.0f}"})
                explained.add(comp)
            if any(f["cause"] in ("addback_over_cap", "addback_not_permitted") for f in findings):
                explained |= {"cons_ebitda", "lev_ratio"}
            # 2. certificate's own arithmetic
            if "cons_ebitda" in comps and "cons_ebitda" not in explained:
                ar = tb.check_certificate_arithmetic()
                if ar and abs(ar["diff"]) > 0.5:
                    findings.append({"component": "cons_ebitda", "cause": "borrower_arithmetic_error",
                                     "citations": [f"certificate:p{comps['cons_ebitda']['cert_page']}"],
                                     "explanation": f"stated {ar['stated_cons_ebitda']:,.0f} vs sum of components "
                                                    f"{ar['sum_of_components']:,.0f}"})
                    explained |= {"cons_ebitda", "lev_ratio"}
            # 3. EBITDA before adjustments
            if "ebitda_pre" in comps:
                pc = tb.check_period_consistency()
                if pc:
                    findings.append({"component": "ebitda_pre", "cause": "period_restatement_mismatch",
                                     "citations": [f"financials:p{d['current_page']} ({d['quarter']} {d['line']} "
                                                   f"restated by {d['delta']:,.0f} vs {d['prior_period']} package)" for d in pc],
                                     "explanation": "certificate appears to use pre-restatement figures"})
                else:
                    sv = tb.compare_statement_to_certificate("ebitda_pre")
                    findings.append({"component": "ebitda_pre", "cause": "statement_certificate_mismatch",
                                     "citations": [f"certificate:p{sv['cert_page']}"], "explanation": "differs from statements"})
                explained |= {"ebitda_pre", "cons_ebitda", "lev_ratio"}
            # 4. debt
            if "debt" in comps:
                x = tb.xbrl_tieout("total_debt")
                if x and not x["tied"]:
                    r = tb.request_reextraction("total_debt")
                    findings.append({"component": "debt", "cause": "extraction_error_suspected",
                                     "citations": [f"financials:p{x['page']}"], "explanation": json.dumps(r)})
                else:
                    sv = tb.compare_statement_to_certificate("debt")
                    findings.append({"component": "debt", "cause": "statement_certificate_mismatch",
                                     "citations": [f"financials:p{x['page'] if x else '?'} (XBRL-tied)",
                                                   f"certificate:p{sv['cert_page']}"],
                                     "explanation": f"statement {sv['statement']:,.0f} vs certificate {sv['certificate']:,.0f}"})
                explained |= {"debt", "lev_ratio"}
            if "interest" in comps:
                findings.append({"component": "interest", "cause": "statement_certificate_mismatch", "citations": [],
                                 "explanation": "interest differs from statements"})
                explained.add("interest")
            for comp in comps:
                if comp not in explained:
                    findings.append({"component": comp, "cause": "unresolved", "citations": [],
                                     "explanation": "no closed-set cause found"})
        except BudgetExceeded:
            findings.append({"component": "*", "cause": "unresolved", "citations": [],
                             "explanation": f"step budget of {tb.budget} exhausted"})
        return findings


def get_investigator(backend):
    if backend == "claude":
        from cov.agent_llm import ClaudeInvestigator
        return ClaudeInvestigator()
    return RuleInvestigator()
