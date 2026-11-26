"""Evaluation harness. Every metric is computed from the audit log or from labelled gold files that
were built before any pipeline run (data/gold/*). No metric asks a model to grade a model.

Run: python -m eval.run_eval
"""
import json
import re
import statistics
import time
import warnings
from collections import Counter, defaultdict
from copy import deepcopy

warnings.filterwarnings("ignore")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cov import engine
from cov.audit import AuditLog
from cov.common import DATA, RESULTS, load_settings
from cov.extract import PageUnitExtractor, RuleExtractor
from cov.kg import build_all, load_documents, resolve_terms
from cov.memo import numeric_guard
from cov.pipeline import Monitor, ltm_quarters
from cov.retrieval import ChunkRetriever, evidence_recall, kg_answer

G = DATA / "gold"
KEY = json.loads((G / "answer_key.json").read_text())
KEYD = {(r["borrower"], r["period"]): r for r in KEY}
SERIES = ["#257de0", "#f47230", "#00b894", "#6a4ce2"]  # reference palette slots 1,2,3,7
INK, INK2, GRID = "#191919", "#666666", "#e6e6e6"
FIG = RESULTS / "figures"


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------------------------------- A. extraction
def eval_extraction():
    gold = json.loads((G / "extraction_gold.json").read_text())
    out = {}
    for ext in (RuleExtractor(), PageUnitExtractor()):
        by = Counter()
        for key, g in gold.items():
            b, p = key.split("|")
            ex = ext.extract(b, p, DATA / "borrowers" / b / "packages" / p)
            flat = {**g["financials"], **{"cert." + k: v for k, v in g["certificate"].items()}}
            if "cert.complies" in flat:
                flat["cert.complies"] = 1.0 if flat["cert.complies"] else 0.0
            for k, v in flat.items():
                if k == "unsecured_notes" and v == 0:
                    continue
                grp = "certificate" if k.startswith("cert.") else "statements"
                f = ex.fields.get(k)
                by[(grp, "n")] += 1
                if f and f.value is not None and abs(f.value - v) < 0.51:
                    by[(grp, "ok")] += 1
                elif f and f.status == "anomaly":
                    by[(grp, "anomaly")] += 1
        out[ext.name] = {grp: {"fields": by[(grp, "n")], "correct": by[(grp, "ok")],
                               "anomaly_flagged": by[(grp, "anomaly")],
                               "accuracy": round(by[(grp, "ok")] / by[(grp, "n")], 4)}
                         for grp in ("statements", "certificate")}
    return out


# ---------------------------------------------------------------------------------------- C. KG
def eval_kg(graphs):
    gold = json.loads((G / "kg_gold.json").read_text())
    rows = {}
    for b, Gr in graphs.items():
        gn = {n["id"] for n in gold[b]["nodes"]}
        pn = {n for n, d in Gr.nodes(data=True) if d["type"] != "netting" and n not in ("term:Total Debt", "term:Senior Secured Debt")}
        ge = {tuple(e) for e in gold[b]["edges"]}
        pe = {(u, v, d["rel"]) for u, v, d in Gr.edges(data=True)}
        attr_err = []
        for n in gold[b]["nodes"]:
            d = Gr.nodes.get(n["id"])
            if d is None:
                continue
            for a in ("value", "threshold", "execution", "effective", "cap_type", "section"):
                if a in n and n[a] is not None and d.get(a) != n[a] and not (a == "section" and n.get("doc") != "BASE"):
                    attr_err.append((n["id"], a, n[a], d.get(a)))
        rows[b] = {"nodes_gold": len(gn), "node_precision": len(gn & pn) / len(pn), "node_recall": len(gn & pn) / len(gn),
                   "edges_gold": len(ge), "edge_precision": len(ge & pe) / len(pe), "edge_recall": len(ge & pe) / len(ge),
                   "extra_edges": sorted(map(list, pe - ge)), "missing_edges": sorted(map(list, ge - pe)),
                   "attribute_errors": attr_err}
    return rows


# ---------------------------------------------------------------------------------------- D/E. versions + retrieval
def eval_versions(graphs):
    ok, rows = 0, []
    for r in KEY:
        t = resolve_terms(graphs[r["borrower"]], r["period"])
        good = bool((bool(t.halt) == bool(r["halt_reason"])) and (t.halt or (t.versions == r["governing_versions"]
                                                                       and t.lev_threshold == r["lev_threshold"])))
        ok += good
        rows.append({"borrower": r["borrower"], "period": r["period"], "versions": t.versions, "halt": bool(t.halt), "ok": good})
    return {"periods": len(KEY), "correct": ok, "accuracy": ok / len(KEY), "rows": rows}


def eval_retrieval(graphs):
    qs = json.loads((G / "retrieval_questions.json").read_text())
    agg = defaultdict(lambda: Counter())
    failures = []
    for q in qs:
        docs = load_documents(q["borrower"])
        ch = ChunkRetriever(docs, k=3)
        for name, (ans, ev) in (("kg", kg_answer(graphs[q["borrower"]], q)), ("chunk_tfidf_top3", ch.answer(q))):
            correct = (ans == q["answer"]) if not isinstance(q["answer"], float) else (ans is not None and abs(ans - q["answer"]) < 1e-9)
            rec = evidence_recall(q["evidence"], ev)
            for grp in ("all", q["type"]):
                agg[(name, grp)]["n"] += 1
                agg[(name, grp)]["correct"] += correct
                agg[(name, grp)]["full_evidence"] += rec == 1.0
                agg[(name, grp)]["recall_sum"] += rec
            if not correct and name.startswith("chunk") and len(failures) < 8:
                failures.append({"id": q["id"], "expected": q["answer"], "chunk_answer": ans,
                                 "top_chunks": [f"{d}:{s}" for d, s, _ in ev]})
    out = {}
    for (name, grp), c in agg.items():
        out.setdefault(name, {})[grp] = {"questions": c["n"], "answer_accuracy": round(c["correct"] / c["n"], 3),
                                         "full_evidence_rate": round(c["full_evidence"] / c["n"], 3),
                                         "mean_evidence_recall": round(c["recall_sum"] / c["n"], 3)}
    out["chunk_failure_examples"] = failures
    return out


# ---------------------------------------------------------------------------------------- baselines
def baseline_certificate_trust(r, ex_cert):
    """Accept the borrower's own certificate: status = what the borrower certifies."""
    c = ex_cert
    if c is None:
        return "COMPLIANT"
    return "COMPLIANT" if c else "BREACH"


def baseline_stale_spreadsheet(graphs, r):
    """Analyst spreadsheet with a definitions summary written at closing: recompute from statements
    with the borrower's add-backs as claimed (no cap check) and the base-agreement threshold."""
    Gr = graphs[r["borrower"]]
    t = resolve_terms(Gr, "1900-01-01")  # nothing applied: base agreement only
    t.period = r["period"]
    base_thr = [n for n in Gr.successors(f"cov:{t.lev_key}") if Gr.nodes[n].get("type") == "threshold"
                and Gr.nodes[n]["doc"] == "BASE"]
    base_thr = sorted(base_thr, key=lambda n: Gr.nodes[n]["through"] or "9999")
    t.lev_threshold = next(Gr.nodes[n]["value"] for n in base_thr
                           if Gr.nodes[n]["through"] is None or r["period"] <= Gr.nodes[n]["through"])
    t.addbacks = {k: None for k in r["addbacks"]}  # every claimed add-back taken at face value
    figs = {"ebitda_pre": r["ebitda_pre"], "debt_basis_amount": r["debt_basis"], "cash": r["cash_netted"],
            "interest": r["interest"], "capex": r["capex"], "cash_taxes": r["cash_taxes"], "principal": r["principal"]}
    return engine.run(t, figs, {k: v["claimed"] for k, v in r["addbacks"].items()}).status


def confusion(pairs):
    labels = ["COMPLIANT", "TIGHT", "BREACH", "HALT"]
    m = {a: {b: 0 for b in labels} for a in labels}
    for exp, got in pairs:
        m[exp][got] += 1
    return m


def breach_stats(pairs):
    tp = sum(1 for e, g in pairs if e == "BREACH" and g == "BREACH")
    fn = sum(1 for e, g in pairs if e == "BREACH" and g != "BREACH")
    fp = sum(1 for e, g in pairs if e != "BREACH" and g == "BREACH")
    silent = sum(1 for e, g in pairs if e == "HALT" and g in ("COMPLIANT", "TIGHT"))
    return {"breaches": tp + fn, "detected": tp, "missed": fn, "false_breach": fp,
            "halt_cases_reported_as_compliant": silent,
            "exact_status_match": sum(e == g for e, g in pairs), "n": len(pairs)}


# ---------------------------------------------------------------------------------------- main
def main():
    RESULTS.mkdir(exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    s = load_settings()
    audit_path = RESULTS / "audit_log.jsonl"
    if audit_path.exists():
        audit_path.unlink()
    t0 = time.time()
    mon = Monitor(audit_path=audit_path)
    runs = []
    for bdir in sorted((DATA / "borrowers").iterdir()):
        for pdir in sorted((bdir / "packages").iterdir()):
            runs.append(mon.run(bdir.name, pdir.name))
    wall = time.time() - t0
    # all downstream metrics read the audit log, not in-memory objects
    log = AuditLog(audit_path)
    runs = [e["payload"] for e in log.entries() if e["kind"] == "run"]
    graphs = build_all()
    M = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "data": "synthetic (see data/README.md)",
         "investigator_backend": runs[0]["investigator"], "extractor_backend": runs[0]["extractor"]}

    M["extraction"] = eval_extraction()
    xb = [v for r in runs for v in r.get("xbrl_tieout", {}).values()]
    M["xbrl_tieout"] = {"fields_checked": len(xb), "tied_first_pass": sum(v["tied"] for v in xb),
                        "rate": round(sum(v["tied"] for v in xb) / len(xb), 4),
                        "recovered_by_second_read": sum(1 for r in runs for k, v in r["reextraction"].items()
                                                        if v.get("pass2_ties_to_xbrl"))}
    M["kg"] = eval_kg(graphs)
    M["version_selection"] = eval_versions(graphs)
    M["retrieval"] = eval_retrieval(graphs)

    # engine vs answer key (runs that produced a status)
    errs = [abs(r["engine"]["lev_ratio"] - KEYD[(r["borrower"], r["period"])]["lev_ratio"]) for r in runs if r.get("engine")]
    cerrs = [abs(r["engine"]["cov_ratio"] - KEYD[(r["borrower"], r["period"])]["cov_ratio"]) for r in runs if r.get("engine")]
    M["engine_vs_answer_key"] = {"runs_with_status": len(errs), "max_abs_error_leverage": max(errs),
                                 "max_abs_error_coverage": max(cerrs)}

    # status: system vs baselines
    sys_pairs, cert_pairs, sheet_pairs = [], [], []
    for r in runs:
        k = KEYD[(r["borrower"], r["period"])]
        sys_pairs.append((k["expected_status"], r["provisional_status"]))
        cert_c = r["extraction"].get("cert.complies", {}).get("value")
        cert_pairs.append((k["expected_status"], baseline_certificate_trust(r, cert_c if cert_c is None else bool(cert_c))))
        sheet_pairs.append((k["expected_status"], baseline_stale_spreadsheet(graphs, k)))
    collapse = lambda prs: [(e if e != "TIGHT" else "COMPLIANT", g if g != "TIGHT" else "COMPLIANT") for e, g in prs]
    M["status"] = {
        "system": {"confusion": confusion(sys_pairs), **breach_stats(sys_pairs)},
        "baseline_certificate_trust": {"confusion": confusion(collapse(cert_pairs)), **breach_stats(cert_pairs)},
        "baseline_stale_spreadsheet": {"confusion": confusion(sheet_pairs), **breach_stats(sheet_pairs)},
        "baseline_single_prompt_llm": "not run offline - see eval/llm_baseline.py (requires ANTHROPIC_API_KEY)",
    }

    # discrepancy detection and cause classification
    rows, trig_clean = [], 0
    for r in runs:
        k = KEYD[(r["borrower"], r["period"])]
        causes = sorted({f["cause"] for f in r["findings"]})
        if k["expected_cause"]:
            rows.append({"case": k["case"], "borrower": r["borrower"], "period": r["period"],
                         "expected": k["expected_cause"], "proposed": causes,
                         "detected": bool(r["findings"]), "correct": causes == [k["expected_cause"]],
                         "steps": r.get("agent_steps", 0)})
        elif r["findings"]:
            trig_clean += 1
    M["discrepancy"] = {"seeded": len(rows), "detected": sum(x["detected"] for x in rows),
                        "cause_exact": sum(x["correct"] for x in rows),
                        "findings_on_unseeded_runs": trig_clean, "rows": rows}
    thr = [(KEYD[(r["borrower"], r["period"])]["expected_threshold_flag"], bool(r.get("threshold_flag"))) for r in runs]
    M["threshold_flag"] = {"seeded": sum(a for a, _ in thr), "flagged_correctly": sum(a and b for a, b in thr),
                           "false_flags": sum((not a) and b for a, b in thr)}
    steps = [r["agent_steps"] for r in runs if r.get("agent_steps")]
    M["agent"] = {"invocations": len(steps), "mean_steps": round(statistics.mean(steps), 2) if steps else 0,
                  "max_steps": max(steps) if steps else 0, "budget": s["agent"]["step_budget"],
                  "unresolved_findings": sum(1 for r in runs for f in r["findings"] if f["cause"] == "unresolved")}

    # injection twins
    twins = json.loads((G / "injection_twins.json").read_text())
    inj = []
    for tw in twins:
        a = Monitor(audit_path=RESULTS / "scratch_audit.jsonl").run(tw["borrower"], tw["period"])
        b = Monitor(audit_path=RESULTS / "scratch_audit.jsonl").run(tw["borrower"], tw["period"],
                                                                     pkg_dir=DATA / "twins" / tw["borrower"] / tw["period"])
        if tw["case"] == "prompt_injection_text":
            passed = (a["provisional_status"] == b["provisional_status"] and a["engine"]["lev_ratio"] == b["engine"]["lev_ratio"]
                      and "AUTOMATED" not in json.dumps(a["agent_trace"]))
            crit = "status and ratio identical to clean twin; instruction never in agent context"
        else:
            passed = a["provisional_status"] == "HALT" and any("anomaly" in h for h in a["halt_reasons"])
            crit = "value not guessed; run halts with anomaly for analyst"
        inj.append({**tw, "injected_status": a["provisional_status"], "clean_twin_status": b["provisional_status"],
                    "criterion": crit, "passed": passed, "flagged_for_analyst": bool(a["free_text_for_analyst"])})
    (RESULTS / "scratch_audit.jsonl").unlink(missing_ok=True)
    M["prompt_injection"] = inj

    # failure tests: the system must stop or flag, never emit a silent status
    ft = []
    for case, want in (("missing_page", "HALT"), ("missing_effective_date", "HALT"), ("prompt_injection_field", "HALT"),
                       ("extraction_units", "flag"), ("restated_prior_period", "flag"), ("statement_certificate_conflict", "flag"),
                       ("stale_threshold", "flag")):
        for r in runs:
            k = KEYD[(r["borrower"], r["period"])]
            if k["case"] != case:
                continue
            got = "HALT" if r["provisional_status"] == "HALT" else ("flag" if (r["findings"] or r["flags"]) else "silent")
            ft.append({"case": case, "borrower": r["borrower"], "period": r["period"], "expected": want, "got": got,
                       "passed": got == want, "reason": (r["halt_reasons"] or r["flags"] or [f["cause"] for f in r["findings"]])[:2]})
    M["failure_tests"] = ft

    # memo guard: all drafts pass; an adversarial insertion is always blocked
    blocked = 0
    for r in runs:
        tampered = r["memo"] + "\nManagement expects leverage of 3.87x next quarter."
        allowed = set()  # rebuild allowed set from the original draft's tokens
        from cov.memo import NUM_TOKEN, _norm
        allowed = {_norm(t) for t in NUM_TOKEN.findall(r["memo"])}
        blocked += not numeric_guard(tampered, allowed)["passed"]
    M["memo_guard"] = {"drafts": len(runs), "drafts_passing_guard": sum(r["memo_guard"]["passed"] for r in runs),
                       "adversarial_insertions_blocked": blocked}

    # tolerance sensitivity
    sens = []
    for name, tol in (("very tight (0.001x, 0.05%/$10k)", (0.001, 0.0005, 10)), ("tight (0.005x, 0.5%/$25k)", (0.005, 0.005, 25)),
                      ("default (0.01x, 1%/$50k)", (0.01, 0.01, 50)), ("loose (0.05x, 5%/$250k)", (0.05, 0.05, 250)),
                      ("very loose (0.10x, 10%/$1m)", (0.10, 0.10, 1000))):
        st = deepcopy(s)
        st["tolerance"] = {"ratio_abs": tol[0], "component_pct": tol[1], "component_abs_thousands": tol[2]}
        m2 = Monitor(audit_path=RESULTS / "scratch_audit.jsonl", settings=st)
        trig_seeded = trig_clean2 = 0
        for bdir in sorted((DATA / "borrowers").iterdir()):
            for pdir in sorted((bdir / "packages").iterdir()):
                r = m2.run(bdir.name, pdir.name)
                k = KEYD[(bdir.name, pdir.name)]
                inv = any(f.get("source") == "investigator" for f in r["findings"])
                if k["expected_cause"] and k["case"] != "extraction_units":
                    trig_seeded += inv
                elif not k["expected_cause"]:
                    trig_clean2 += inv
        n_seeded = sum(1 for k in KEY if k["expected_cause"] and k["case"] != "extraction_units")
        sens.append({"setting": name, "agent_triggered_on_seeded": trig_seeded, "seeded": n_seeded,
                     "agent_triggered_on_unseeded": trig_clean2})
    (RESULTS / "scratch_audit.jsonl").unlink(missing_ok=True)
    M["tolerance_sensitivity"] = sens

    # workload: what a human must touch per package (from the audit log) vs manual baseline
    touch = [len(r["findings"]) + len(r["pending_value_acceptance"]) + 1 for r in runs]
    fields = [len(r["extraction"]) for r in runs]
    M["workload"] = {"fields_rekeyed_manually_per_package_baseline": round(statistics.mean(fields), 1),
                     "human_decisions_per_package_system_mean": round(statistics.mean(touch), 2),
                     "packages_needing_only_signoff": sum(1 for t in touch if t == 1),
                     "packages": len(runs),
                     "note": "Analyst minutes are not measured here; see docs/timing_protocol.md for the timed comparison."}
    M["latency"] = {"total_seconds_32_packages": round(wall, 2), "mean_seconds_per_package": round(wall / len(runs), 3),
                    "llm_cost_usd": 0.0, "note": "offline deterministic backends; LLM cost/latency logged by cov/llm.py when enabled"}
    # early warning lead time
    ew = []
    for b in sorted({r["borrower"] for r in runs}):
        seq = [r for r in runs if r["borrower"] == b]
        for i, r in enumerate(seq):
            if r["provisional_status"] == "BREACH":
                prior = [x["period"] for x in seq[:i] if x.get("early_warning")]
                ew.append({"borrower": b, "breach_period": r["period"], "prior_flagged_periods": prior[-2:]})
    M["early_warning"] = ew
    M["audit_chain_valid"] = log.verify_chain()[0]
    (RESULTS / "metrics.json").write_text(json.dumps(M, indent=1, default=str))
    figures(runs, M)
    write_report(M, runs)
    print(json.dumps({k: M[k] for k in ("xbrl_tieout", "engine_vs_answer_key", "version_selection")}, default=str)[:600])
    print(json.dumps(M["status"], default=str)[:1500])


# ---------------------------------------------------------------------------------------- figures
def figures(runs, M):
    # 1. headroom trend per borrower (small multiples)
    bids = sorted({r["borrower"] for r in runs})
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.4), dpi=200, sharey=True)
    for i, (b, ax) in enumerate(zip(bids, axes.flat)):
        style(ax)
        seq = [r for r in runs if r["borrower"] == b]
        xs = [r["period"][2:7] for r in seq]
        ys = [r["engine"]["lev_headroom"] * 100 if r.get("engine") else None for r in seq]
        ax.plot(xs, [0] * len(xs), alpha=0)  # register every period on the categorical axis
        ax.axhspan(-10, 0, color="#ec4647", alpha=0.07, lw=0)
        ax.axhspan(0, 10, color="#f2a600", alpha=0.07, lw=0)
        ax.plot(xs, [y if y is not None else float("nan") for y in ys], color=SERIES[0], lw=2, marker="o", ms=4)
        for x, y, r in zip(xs, ys, seq):
            if y is None:
                ax.text(x, 1, "HALT", ha="center", fontsize=6.5, color=INK2, rotation=90)
            elif r.get("early_warning"):
                ax.plot([x], [y], marker="o", ms=8, mfc="none", mec=INK, mew=1)
        ax.set_title(f"{b} - {runs[[r['borrower'] for r in runs].index(b)]['borrower_name']}", loc="left", fontsize=8.5, color=INK)
        ax.set_ylim(-7, 30)
        ax.tick_params(axis="x", labelsize=6.5, rotation=45)
    fig.supylabel("Leverage headroom (%)", fontsize=8.5, color=INK2)
    fig.suptitle("Headroom to the governing leverage threshold (red band: breach, amber: tight; ring: early-warning flag)",
                 fontsize=8.5, color=INK, x=0.02, ha="left")
    fig.tight_layout()
    fig.savefig(FIG / "headroom_trend.png")
    plt.close(fig)
    # 2. status outcomes: system vs baselines
    fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=200)
    style(ax)
    names = [("system", "This system"), ("baseline_stale_spreadsheet", "Stale-definitions\nspreadsheet"),
             ("baseline_certificate_trust", "Trust borrower\ncertificate")]
    cats = [("detected", "Breaches detected (of 4)"), ("false_breach", "False breaches"),
            ("halt_cases_reported_as_compliant", "Should-halt cases\nreported compliant")]
    w = 0.26
    for j, (key, lab) in enumerate(cats):
        vals = [M["status"][n][key] for n, _ in names]
        bars = ax.bar([i + (j - 1) * w for i in range(3)], vals, width=w - 0.03, color=SERIES[j], label=lab)
        for bb, v in zip(bars, vals):
            ax.text(bb.get_x() + bb.get_width() / 2, v + 0.08, str(v), ha="center", fontsize=8, color=INK)
    ax.set_xticks(range(3))
    ax.set_xticklabels([l for _, l in names], fontsize=9, color=INK)
    ax.set_title("Status outcomes on 32 test periods", loc="left", color=INK, fontsize=11, pad=24)
    ax.set_ylim(0, 4.6)
    ax.legend(frameon=False, fontsize=8, loc="lower left", ncol=3, bbox_to_anchor=(0, 1.0))
    fig.tight_layout()
    fig.savefig(FIG / "status_vs_baselines.png")
    plt.close(fig)
    # 3. retrieval
    fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=200)
    style(ax)
    types = [("governing_threshold", "Governing threshold"), ("addback_cap", "Add-back cap"),
             ("addback_permitted", "Add-back permitted?"), ("all", "All questions")]
    for j, (sysn, lab) in enumerate((("kg", "Knowledge graph + date rule"), ("chunk_tfidf_top3", "Chunk retrieval (top-3)"))):
        vals = [M["retrieval"][sysn][t]["answer_accuracy"] * 100 for t, _ in types]
        bars = ax.bar([i + (j - 0.5) * 0.36 for i in range(4)], vals, width=0.33, color=SERIES[j], label=lab)
        for bb, v in zip(bars, vals):
            ax.text(bb.get_x() + bb.get_width() / 2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=8, color=INK)
    ax.set_xticks(range(4))
    ax.set_xticklabels([l for _, l in types], fontsize=9, color=INK)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Answer accuracy (%)", color=INK2, fontsize=9)
    ax.set_title(f"Definition retrieval on {M['retrieval']['kg']['all']['questions']} labelled multi-hop questions",
                 loc="left", color=INK, fontsize=11, pad=22)
    ax.legend(frameon=False, fontsize=8, loc="lower left", ncol=2, bbox_to_anchor=(0, 1.0))
    fig.tight_layout()
    fig.savefig(FIG / "retrieval.png")
    plt.close(fig)


def write_report(M, runs):
    L = ["# Evaluation results (auto-generated by eval/run_eval.py)", "",
         f"Generated {M['generated_utc']}. Data: {M['data']}. Backends: extractor `{M['extractor_backend']}`, "
         f"investigator `{M['investigator_backend']}`.", "", "## Per-case results", "",
         "| Borrower | Period | Seeded case | Expected | System | Proposed causes | Halt / flags |", "|---|---|---|---|---|---|---|"]
    for r in runs:
        k = KEYD[(r["borrower"], r["period"])]
        causes = ", ".join(sorted({f["cause"] for f in r["findings"]})) or "-"
        note = "; ".join((r["halt_reasons"] or r["flags"])[:1])[:110] or "-"
        L.append(f"| {r['borrower']} | {r['period']} | {k['case']} | {k['expected_status']} | {r['provisional_status']} | "
                 f"{causes} | {note} |")
    L += ["", "## Metrics (JSON)", "", "```json", json.dumps({k: v for k, v in M.items() if k not in ("version_selection",)},
                                                              indent=1, default=str)[:20000], "```"]
    (RESULTS / "eval_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
