"""End-to-end run for one borrower test period.

  Generate/Propose : extraction (typed fields), KG built from the agreement, agent findings, memo prose
  Verify           : completeness, anomalies, XBRL tie-out, second-pass re-read, period consistency,
                     statement-vs-certificate, certificate arithmetic, threshold check
  Constrain        : governing terms resolved by effective date; add-back caps; halt rules
  Decide           : deterministic engine -> provisional status
  Gate / Authorize : approval.ApprovalGate (humans only)
  Act / Record     : append-only audit log; nothing is sent to the borrower by the system
"""
import time
import uuid
from pathlib import Path

from cov import engine, verify
from cov.agent import Toolbox, get_investigator
from cov.audit import AuditLog, git_commit, sha256_file
from cov.common import DATA, RESULTS, load_settings
from cov.extract import PageUnitExtractor, RuleExtractor, completeness
from cov.kg import RuleKGBuilder, load_documents, resolve_terms
from cov.memo import draft

QUARTER_ENDS = ["03-31", "06-30", "09-30", "12-31"]


def ltm_quarters(period):
    y, md = int(period[:4]), period[5:]
    i = QUARTER_ENDS.index(md)
    out = []
    for k in range(3, -1, -1):
        j = i - k
        yy = y + (j // 4)
        out.append(f"{yy}-{QUARTER_ENDS[j % 4]}")
    return out


class Monitor:
    def __init__(self, audit_path=None, extractor=None, investigator=None, kg_builder=None, settings=None,
                 data_root=None):
        self.settings = settings or load_settings()
        self.audit = AuditLog(audit_path or RESULTS / "audit_log.jsonl")
        self.extractor = extractor or self._default_extractor()
        self.second = PageUnitExtractor()
        self.investigator = investigator or get_investigator(self.settings["agent"]["backend"])
        self.kg_builder = kg_builder or RuleKGBuilder()
        self.data_root = Path(data_root or DATA)
        self.graphs, self.prior, self.history = {}, {}, {}

    def _default_extractor(self):
        if self.settings["extraction"]["backend"] == "claude":
            from cov.extract_llm import ClaudeExtractor
            return ClaudeExtractor()
        return RuleExtractor()

    def graph(self, borrower):
        if borrower not in self.graphs:
            self.graphs[borrower] = self.kg_builder.build(borrower, load_documents(borrower, self.data_root / "borrowers" / borrower / "agreement"))
        return self.graphs[borrower]

    # ------------------------------------------------------------------------------------------
    def run(self, borrower, period, pkg_dir=None, borrower_name=None, received=None):
        t0 = time.time()
        s = self.settings
        pkg_dir = Path(pkg_dir or self.data_root / "borrowers" / borrower / "packages" / period)
        quarters = ltm_quarters(period)
        G = self.graph(borrower)
        terms = resolve_terms(G, period)
        ex = self.extractor.extract(borrower, period, pkg_dir)
        facts = verify.load_xbrl(borrower) if (self.data_root / "borrowers" / borrower / "xbrl_companyfacts.json").exists() else None
        rec = {"run_id": str(uuid.uuid4()), "borrower": borrower, "borrower_name": borrower_name or G.graph.get("borrower"),
               "period": period, "engine_version": engine.ENGINE_VERSION, "code_commit": git_commit(),
               "extractor": self.extractor.name, "investigator": self.investigator.name, "kg_builder": self.kg_builder.name,
               "settings": {"tolerance": s["tolerance"], "xbrl_tieout_pct": s["xbrl_tieout_pct"],
                            "tight_headroom": s["tight_headroom"], "step_budget": s["agent"]["step_budget"]},
               "input_hashes": {f.name: sha256_file(f) for f in sorted(pkg_dir.glob("*.pdf"))},
               "terms": terms.to_dict(), "halt_reasons": [], "flags": [], "findings": [], "agent_trace": [],
               "pending_value_acceptance": [], "reextraction": {}, "free_text_for_analyst": ex.free_text,
               "delivery": verify.delivery_check(period, received)}
        bname = G.graph.get("borrower_name", borrower)
        rec["borrower_name"] = borrower_name or bname
        if rec["delivery"]["late"]:
            rec["flags"].append(f"package received {rec['delivery']['received']} after due date {rec['delivery']['due']}")

        # ---------------- Verify: completeness, anomalies
        missing, anomalies = completeness(ex, quarters)
        if missing:
            rec["halt_reasons"].append(f"required fields missing: {', '.join(missing[:8])}"
                                       + (" ..." if len(missing) > 8 else "")
                                       + f" (certificate pages received: {ex.pages.get('certificate')})")
        if anomalies:
            for k in anomalies:
                f = ex.fields[k]
                rec["halt_reasons"].append(f"anomaly in {k} ({f.doc} p{f.page}): non-numeric content in a numeric "
                                           f"field; value left empty, shown to analyst")
        if terms.halt:
            rec["halt_reasons"].append(terms.halt)

        # ---------------- Verify: XBRL tie-out, with an independent second read on failure
        xb = verify.xbrl_tieout(ex, facts, period, s["xbrl_tieout_pct"]) if facts else {}
        rec["xbrl_tieout"] = xb
        failed = {fname: r for fname, r in xb.items() if not r["tied"]}
        if failed:
            # independent second read of the whole document; any field on an affected page that
            # reads differently is replaced by a *recommended* value pending analyst acceptance
            ex2 = self.second.extract(borrower, period, pkg_dir)
            pages = {(ex.fields[f].doc, ex.fields[f].page) for f in failed}
            for fname, r in failed.items():
                v2 = ex2.fields.get(fname).value if ex2.fields.get(fname) else None
                ties2 = v2 is not None and abs(v2 - r["xbrl"]) <= s["xbrl_tieout_pct"] * abs(r["xbrl"])
                rec["reextraction"][fname] = {"pass1": r["extracted"], "pass2": v2, "xbrl": r["xbrl"],
                                              "pass2_ties_to_xbrl": ties2, "page": r["page"],
                                              "trigger": "xbrl_tieout_failed"}
                if not ties2:
                    rec["halt_reasons"].append(f"{fname} fails XBRL tie-out on both reads (pass1 {r['extracted']}, "
                                               f"pass2 {v2}, XBRL {r['xbrl']})")
            if not rec["halt_reasons"]:
                changed = []
                for k, f in ex.fields.items():
                    f2 = ex2.fields.get(k)
                    if (f.doc, f.page) in pages and f2 is not None and f2.value is not None and f.value != f2.value:
                        rec["reextraction"].setdefault(k, {"pass1": f.value, "pass2": f2.value, "page": f.page,
                                                           "trigger": "same page as tie-out failure"})
                        f.value = f2.value
                        f.extractor = "pagewise_pass2 (pending analyst acceptance)"
                        if f.verification == "xbrl_failed":
                            f.verification = "xbrl_tied_after_reextraction"
                        changed.append(k)
                rec["pending_value_acceptance"] = changed
                (doc, pg), = list(pages)[:1] or [("?", "?")]
                rec["findings"].append({"component": ", ".join(changed), "cause": "extraction_error_suspected",
                                        "source": "verification",
                                        "citations": [f"{doc}:p{pg}", "XBRL companyfacts"],
                                        "explanation": "; ".join(f"{k}: pass 1 {rec['reextraction'][k]['pass1']:,.1f} vs "
                                                                 f"pass 2 {rec['reextraction'][k]['pass2']:,.1f}" for k in changed)})
        rec["extraction"] = {k: f.to_dict() for k, f in ex.fields.items()}

        prior = self.prior.get(borrower)
        rec["period_diffs"] = verify.period_consistency(ex, prior, quarters)
        self.prior[borrower] = ex

        if rec["halt_reasons"]:
            return self._finish(rec, "HALT", t0)

        # ---------------- Decide: deterministic engine on page-tied figures
        ebitda_pre = sum(ex.get(f"operating_income_{q}") + ex.get(f"da_{q}") for q in quarters)
        interest = sum(ex.get(f"interest_expense_{q}") for q in quarters)
        basis = (ex.get("revolver") + ex.get("term_loan")) if terms.debt_basis == "secured" else ex.get("total_debt")
        figs = {"ebitda_pre": ebitda_pre, "interest": interest, "debt_basis_amount": basis, "cash": ex.get("cash"),
                "capex": ex.get("capex") or 0.0, "cash_taxes": ex.get("cash_taxes") or 0.0,
                "principal": ex.get("principal") or 0.0}
        claims = {k.split("::", 1)[1]: f.value for k, f in ex.fields.items() if k.startswith("cert.addback::")}
        eng = engine.run(terms, figs, claims, s["tight_headroom"])
        rec["figures"], rec["claims"], rec["engine"] = figs, claims, eng.to_dict()

        # ---------------- Verify: certificate vs engine, threshold, restatement
        comps = verify.certificate_components(ex, eng, figs, s)
        rec["components"] = comps
        thr = verify.threshold_check(ex, terms)
        if thr:
            rec["flags"].append(f"certificate applies {thr['certificate_threshold']:.2f}x; governing threshold is "
                                f"{thr['governing_threshold']:.2f}x under {', '.join(thr['versions'])}")
            rec["threshold_flag"] = thr
        for d in rec["period_diffs"]:
            rec["flags"].append(f"restatement: {d['quarter']} {d['line']} changed by {d['delta']:,.0f} vs "
                                f"{d['prior_period']} package")
        for ln in eng.addbacks:
            if ln["permitted"] < ln["claimed"]:
                rec["flags"].append(f"add-back {ln['name']}: {ln['reason'].replace('_', ' ')} "
                                    f"(claimed {ln['claimed']:,.0f}, permitted {ln['permitted']:,.0f})")
        # ---------------- Propose: bounded investigation when the gap exceeds tolerance
        if any(c["exceeds_tolerance"] for c in comps):
            ctx = {"components": comps, "terms": terms, "engine": eng, "extraction": ex,
                   "period_diffs": rec["period_diffs"], "stmt_vs_cert": verify.statement_vs_certificate(ex, figs),
                   "xbrl": xb, "reextract": lambda fld: rec["reextraction"].get(fld) or
                   (lambda f2: {"pass2": f2.value, "page": f2.page})(self.second.reextract_field(borrower, period, pkg_dir, fld))}
            tb = Toolbox(ctx, s["agent"]["step_budget"])
            found = self.investigator.investigate(tb)
            rec["findings"] += [{**f, "source": "investigator"} for f in found]
            rec["agent_trace"] = tb.trace
            rec["agent_steps"] = len(tb.trace)
        # early warning on reported headroom history
        hist = self.history.setdefault(borrower, [])
        hist.append((period, eng.lev_headroom))
        rec["early_warning"] = engine.early_warning(hist, s)
        return self._finish(rec, eng.status, t0)

    def _finish(self, rec, status, t0):
        rec["provisional_status"] = status
        appr = ["accept or reject each proposed finding (analyst)"] if rec["findings"] else []
        if rec["pending_value_acceptance"]:
            appr.append("accept re-extracted values (analyst)")
        appr.append({"BREACH": "declare breach / consider waiver, amendment or equity cure (credit committee)",
                     "TIGHT": "sign memo and consider watchlist / risk rating (portfolio manager)",
                     "COMPLIANT": "sign memo (portfolio manager)",
                     "HALT": "resolve halt and release (portfolio manager)"}[status])
        appr.append("any communication to the borrower (deal team)")
        rec["required_approvals"] = appr
        memo, guard = draft(rec)
        rec["memo"], rec["memo_guard"] = memo, guard
        if not guard["passed"]:
            rec["memo_blocked"] = True
        rec["latency_s"] = round(time.time() - t0, 3)
        self.audit.append("run", rec)
        return rec


def run_all(audit_path=None, **kw):
    import json
    m = Monitor(audit_path=audit_path, **kw)
    out = []
    for bdir in sorted((m.data_root / "borrowers").iterdir()):
        for pdir in sorted((bdir / "packages").iterdir()):
            out.append(m.run(bdir.name, pdir.name))
    return m, out
