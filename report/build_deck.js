// node report/build_deck.js  -> report/MGT8803_Final_Presentation_Covenant_Monitoring.pptx
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const SKILL = process.env.PPTX_SKILL;
const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));

const ROOT = path.resolve(__dirname, "..");
const M = JSON.parse(fs.readFileSync(path.join(ROOT, "results", "metrics.json")));
const FIG = (f) => path.join(ROOT, "results", "figures", f);
const OUT = path.join(ROOT, "report", "MGT8803_Final_Presentation_Covenant_Monitoring.pptx");

const THEME = {
  name: "Covenant Navy", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "1B2433", lt1: "FFFFFF", dk2: "16324F", lt2: "EEF2F7",
    accent1: "16324F", accent2: "1F8A70", accent3: "E0A100", accent4: "C8423B", accent5: "5B6B82", accent6: "7A5CC8",
    hlink: "1F8A70", folHlink: "5B6B82" },
};
const HEX = THEME.colors;
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Governed Agentic Covenant Monitoring";
const C = pres.SchemeColor;

// ---------- layouts
pres.defineSlideMaster({ title: "DARK_TITLE", background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.1, w: 11.7, h: 1.9, fontSize: 42, bold: true, color: C.background1, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 4.15, w: 11.7, h: 1.8, fontSize: 18, color: C.background2, valign: "top" }, text: "" } },
  ] });
pres.defineSlideMaster({ title: "SECTION", background: { color: C.text2 },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.8, y: 0.6, w: 11.7, h: 1.0, fontSize: 36, bold: true, color: C.background1, align: "left" }, text: "" } }],
  slideNumber: { x: 12.3, y: 6.95, w: 0.6, h: 0.3, fontSize: 10, color: C.background2 } });
pres.defineSlideMaster({ title: "CONTENT", background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.9, fontSize: 28, bold: true, color: C.text2, valign: "middle", align: "left" }, text: "" } },
    { text: { text: "MGT 8803 · Covenant Monitoring · Track 1", options: { x: 0.6, y: 6.95, w: 6, h: 0.3, fontSize: 10, color: C.accent5 } } },
  ],
  slideNumber: { x: 12.3, y: 6.95, w: 0.6, h: 0.3, fontSize: 10, color: C.accent5 } });

let n = 0;
const sec = (title) => pres.addSection({ title });
let curSec = "";
function slide(master, section) {
  if (section !== curSec) { sec(section); curSec = section; }
  return pres.addSlide({ masterName: master, sectionTitle: section });
}
const T = (s, text) => s.addText(text, { placeholder: "title" });
function tx(s, text, o) { s.addText(text, { isTextBox: true, fontSize: 16, color: C.text1, valign: "top", margin: 0.05, objectName: `t${++n}`, ...o }); }
function card(s, x, y, w, h, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill || C.background2 }, line: { color: fill || C.background2 }, objectName: `c${++n}` });
}
function stat(s, x, y, w, big, label, color) {
  tx(s, big, { x, y, w, h: 1.0, fontSize: 54, bold: true, color: color || C.accent1, fontFace: THEME.headFontFace });
  tx(s, label, { x, y: y + 1.0, w, h: 0.8, fontSize: 14, color: C.accent5 });
}
function bullets(s, items, o) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    { isTextBox: true, fontSize: 16, color: C.text1, paraSpaceAfter: 8, valign: "top", objectName: `b${++n}`, ...o });
}
function table(s, rows, o) {
  const hdr = rows[0].map((h) => ({ text: h, options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }));
  s.addTable([hdr, ...rows.slice(1)], { fontSize: 13, color: HEX.dk1, border: { type: "solid", pt: 0.5, color: "C9D2DE" },
    fill: { color: "FFFFFF" }, valign: "middle", margin: 0.06, objectName: `tbl${++n}`, ...o });
}
const img = (s, f, x, y, w) => { const b = fs.readFileSync(FIG(f)); const iw = b.readUInt32BE(16), ih = b.readUInt32BE(20);
  s.addImage({ path: FIG(f), x, y, w, h: (w * ih) / iw, altText: f, objectName: `i${++n}` }); };

const S = M.status;

// 1 title
let s = slide("DARK_TITLE", "Opening");
T(s, "Models propose, code computes, people decide");
s.addText([{ text: "Governed agentic covenant monitoring for a middle-market direct lender", options: { breakLine: true } },
  { text: "MGT 8803 AI in Finance · Track 1: Lending and Private Credit", options: { breakLine: true, fontSize: 14 } },
  { text: "Vivan Jain · Srivant Vishnuvajjala · Vidhi Chaturvedi · Manasi Prasad", options: { fontSize: 14 } }], { placeholder: "body" });
s.addNotes("Open with the one-line thesis. We redesigned the quarterly covenant-compliance cycle so that language models only propose, deterministic code computes and verifies, and named people hold every consequential decision. ~30 seconds.");

// agenda
s = slide("CONTENT", "Opening");
T(s, "Agenda");
[["Problem", "Why covenant breaches hide in definitions"], ["Redesign", "Who proposes, what computes, who decides"],
 ["Governance", "Authority enforced in code and config"], ["Demo", "Four scenes and the approval screen"],
 ["Evidence", "Synthetic benchmark and a real SEC filing check"], ["Path to production", "Shadow first, authority last"]].forEach(([h, d], i) => {
  const x = 0.6 + (i % 3) * 4.1, y = 1.6 + Math.floor(i / 3) * 2.45;
  card(s, x, y, 3.9, 2.2);
  s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: y + 0.3, w: 0.6, h: 0.6, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: `o${++n}` });
  tx(s, String(i + 1), { x: x + 0.3, y: y + 0.3, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0 });
  tx(s, h, { x: x + 1.1, y: y + 0.3, w: 2.6, h: 0.6, fontSize: 19, bold: true, valign: "middle" });
  tx(s, d, { x: x + 0.3, y: y + 1.1, w: 3.4, h: 0.9, fontSize: 15, color: C.accent5 });
});
s.addNotes("Fifteen to twenty minutes: about two on the problem, four on the redesign and governance, five on the demo, four on evidence, two on rollout, then questions.");

// 2 hook
s = slide("CONTENT", "Opening");
T(s, "The certificate says compliant. Is it?");
card(s, 0.6, 1.5, 5.8, 4.9);
tx(s, "Apex Industrial · quarter ending 30 Sep 2025", { x: 0.9, y: 1.7, w: 5.3, h: 0.4, fontSize: 16, bold: true, color: C.accent5 });
stat(s, 0.9, 2.3, 2.6, "4.08x", "Total net leverage on the borrower's certificate");
stat(s, 3.6, 2.3, 2.6, "4.50x", "Maximum the certificate applies");
tx(s, "Officer-certified: \"In compliance with all financial covenants: Yes\"", { x: 0.9, y: 4.6, w: 5.3, h: 0.9, fontSize: 16, italic: true });
card(s, 6.9, 1.5, 5.8, 4.9, "FBEDEC");
tx(s, "What the agreement actually says", { x: 7.2, y: 1.7, w: 5.3, h: 0.4, fontSize: 16, bold: true, color: C.accent4 });
stat(s, 7.2, 2.3, 2.6, "4.35x", "Leverage once the 15% add-back cap is applied", C.accent4);
stat(s, 9.9, 2.3, 2.6, "4.25x", "Threshold after the First Amendment", C.accent4);
tx(s, "Breach by 0.10x: $9.0m of add-backs claimed, $6.0m permitted, and a threshold that changed mid-loan", { x: 7.2, y: 4.6, w: 5.3, h: 1.2, fontSize: 16 });
s.addNotes("Hook. Ask the room before revealing the right side. This is our midpoint worked case, now reproduced exactly by the prototype. Two things hide the breach: an uncapped add-back claim and a superseded threshold. Both are definition problems, not arithmetic problems. ~1.5 min.");

// 3 current state
s = slide("CONTENT", "Workflow");
T(s, "Today: re-key, re-read, recompute, reconcile");
img(s, "current_state.png", 0.5, 1.3, 8.1);
bullets(s, ["P1 Financials re-keyed by hand from PDFs", "P2 EBITDA definition rebuilt from an amended agreement, or a summary that has gone stale",
  "P3 Weak link from a ratio to its clause and page", "P4 Monitoring is reactive", "P5 Add-back judgment varies by analyst",
  "P6 Every input comes from the borrower, so it is untrusted"], { x: 8.8, y: 1.45, w: 4.0, h: 5.2, fontSize: 15 });
s.addNotes("Current state, mapped from EDGAR credit agreements and compliance-certificate exhibits. The internal review chain is our assumption and we say so. Emphasise P2 and P6: they are where breaches hide. ~1.5 min.");

// 4 principle
s = slide("CONTENT", "Workflow");
T(s, "Each step gets the least powerful tool that does it reliably");
const cols = [["Model may propose", C.accent3, ["Typed, page-cited extractions", "Agreement knowledge graph (team-reviewed)", "Closed-set cause for a certificate gap", "Memo prose with no numbers of its own"]],
  ["Code computes and verifies", C.accent2, ["Governing version by effective date", "Add-back caps, ratios, headroom, sensitivity", "XBRL tie-out, second independent read", "Prior-package, arithmetic and threshold checks"]],
  ["People decide", C.accent6, ["Analyst accepts or rejects findings", "PM signs compliant or tight; releases halts", "Credit committee declares breach and waivers", "Deal team talks to the borrower"]]];
cols.forEach(([h, col, items], i) => {
  const x = 0.6 + i * 4.15;
  card(s, x, 1.5, 3.9, 4.9);
  s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: 1.75, w: 0.55, h: 0.55, fill: { color: col }, line: { color: col }, objectName: `o${++n}` });
  tx(s, h, { x: x + 1.0, y: 1.75, w: 2.8, h: 0.55, fontSize: 18, bold: true, valign: "middle" });
  bullets(s, items, { x: x + 0.25, y: 2.55, w: 3.45, h: 3.7, fontSize: 15 });
});
tx(s, "Not used: optimisation (compliance is a test, not a choice among options) and learned risk scores (no labelled defaults; a sensitivity an analyst can recompute is easier to defend).",
  { x: 0.6, y: 6.45, w: 12.1, h: 0.45, fontSize: 13, italic: true, color: C.accent5 });
s.addNotes("This is the core design principle from the assignment's ProveAct framing: reasoning and tool use do not imply authority. Mention what we deliberately did not use and why. ~1.5 min.");

// 5 architecture
s = slide("CONTENT", "Workflow");
T(s, "Future state: nothing above the line has authority");
img(s, "future_state.png", 1.85, 1.3, 9.6);
s.addNotes("Walk left to right. Inputs are untrusted. Orange boxes are model-proposed, blue deterministic, green independent verification, violet human authority. Below the dashed line only people act, and everything lands in a hash-chained audit log. ~1.5 min.");

// 6 governance
s = slide("CONTENT", "Governance");
T(s, "Authority is enforced in code and config, not in a prompt");
table(s, [["Question", "Answer"],
  ["What may the LLM propose?", "Typed values, graph nodes, a cause from 7 fixed options, prose"],
  ["What is independently verified?", "GAAP items vs XBRL; failed pages re-read by a different extractor; prior package; statements; arithmetic"],
  ["What makes a result infeasible?", "Undatable amendment, missing field, anomaly, failed tie-out on both reads: HALT"],
  ["Who has authority?", "Analyst: findings · PM: compliant/tight, halts, rating · Committee: breach, waiver"],
  ["What runs automatically?", "Everything except decisions; the system holds no role"],
  ["What is logged?", "Input hashes, commit, terms + evidence, every field + page, agent trace, each decision"]],
  { x: 0.6, y: 1.45, w: 7.6, colW: [2.6, 5.0], fontSize: 13 });
card(s, 8.6, 1.45, 4.1, 4.9);
tx(s, "Gate checks before any signature", { x: 8.85, y: 1.6, w: 3.7, h: 0.4, fontSize: 16, bold: true });
bullets(s, ["Every finding accepted or rejected", "Re-read values accepted", "Role allowed for this determination", "Signer did not review the findings", "Override needs a written rationale"],
  { x: 8.85, y: 2.15, w: 3.7, h: 3.2, fontSize: 15 });
tx(s, "Separation of duties = different evidence sources, not more LLM calls", { x: 8.85, y: 5.35, w: 3.7, h: 0.9, fontSize: 14, italic: true, color: C.accent2 });
s.addNotes("The assignment's eight governance questions, condensed. Point out that the investigator's tools have no write operations: it cannot change a figure or set a status even if it wanted to. ~1.5 min.");

// 7 demo divider
s = slide("SECTION", "Demo");
T(s, "Live demo");
[["1", "Apex Q3 2025", "Graph -> version rule -> engine -> investigator -> memo. Breach found; every number cites a page"],
 ["2", "Who may sign", "PM refused for breach; reviewer refused as signer; committee signs"],
 ["3", "Apex Q4 2025", "Certificate tells 'automated review systems' to report compliant. Status unchanged vs a clean twin"],
 ["4", "Cedar Q2 2026", "Amendment with no calendar effective date: the system refuses to choose a threshold"],
 ["5", "Approval screen", "Page image behind a citation, accept, sign, audit trail"]].forEach(([k, h, d], i) => {
  const y = 1.9 + i * 0.95;
  s.addShape(pres.shapes.OVAL, { x: 0.8, y, w: 0.6, h: 0.6, fill: { color: C.accent2 }, line: { color: C.accent2 }, objectName: `o${++n}` });
  tx(s, k, { x: 0.8, y, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0 });
  tx(s, h, { x: 1.65, y: y - 0.02, w: 2.6, h: 0.65, fontSize: 18, bold: true, color: C.background1, valign: "middle" });
  tx(s, d, { x: 4.3, y: y - 0.02, w: 8.2, h: 0.65, fontSize: 15, color: C.background2, valign: "middle" });
});
s.addNotes("Run python demo.py in a terminal, then streamlit run app/approval_app.py. Script in docs/demo_script.md. Budget about 5-6 minutes. Backup: the memo and trace are in report Appendix B.");

// 8 walkthrough
s = slide("CONTENT", "Demo");
T(s, "What the system produced for Apex Q3 2025");
table(s, [["", "Borrower certificate", "System (engine)"],
  ["EBITDA before adjustments", "$40.0m", "$40.0m"], ["Add-backs", "$9.0m claimed", "$6.0m (15% cap, §1.01(c))"],
  ["Consolidated EBITDA", "$49.0m", "$46.0m"], ["Net debt", "$200.0m", "$200.0m"],
  ["Total net leverage", "4.08x", "4.35x"], ["Threshold", "4.50x (superseded)", "4.25x (First Amendment)"], ["Result", "Compliant", "BREACH, pending committee"]],
  { x: 0.6, y: 1.45, w: 7.2, colW: [2.6, 2.2, 2.4], fontSize: 14 });
card(s, 8.2, 1.45, 4.5, 4.9);
tx(s, "Investigator: 3 read-only calls", { x: 8.45, y: 1.6, w: 4.0, h: 0.4, fontSize: 16, bold: true });
tx(s, [{ text: "1  list_discrepancies()", options: { breakLine: true } }, { text: "2  get_addback_terms('Pro Forma Cost Savings')", options: { breakLine: true } },
  { text: "3  check_cap('Pro Forma Cost Savings')", options: { breakLine: true } }, { text: " ", options: { breakLine: true } },
  { text: "-> addback_over_cap [BASE §1.01(c); certificate p2]" }], { x: 8.45, y: 2.1, w: 4.0, h: 1.9, fontSize: 13, fontFace: "Courier New" });
bullets(s, ["Sensitivity: +$1.06m EBITDA or -$4.5m net debt to comply", "Early-warning flag fired the quarter before", "Threshold flag: certificate used 4.50x"],
  { x: 8.45, y: 4.1, w: 4.0, h: 2.1, fontSize: 14 });
s.addNotes("Backup slide for the demo, or use it if the demo fails. The agent sees typed numbers and citations only. It never sees the certificate's text.");

// 9 eval design
s = slide("CONTENT", "Evaluation");
T(s, "Evaluation: an answer key built before any run");
stat(s, 0.8, 1.6, 2.8, "32", "borrower-quarters (4 borrowers × 8)");
stat(s, 3.8, 1.6, 2.8, "13", "seeded case types, plus 15 clean quarters");
stat(s, 6.8, 1.6, 2.8, "47", "labelled multi-hop definition questions");
stat(s, 9.8, 1.6, 2.8, "0", "metrics that ask an LLM to grade an LLM");
bullets(s, ["Answer key computed by separate code from the engine; every system metric read from the audit log",
  "Baselines: trust the certificate · spreadsheet with a stale definitions summary · chunk retrieval (TF-IDF top-3) · single-prompt LLM (coded, not yet run: no API access in our build environment)",
  "Data is synthetic, written in EDGAR Exhibit-10 structure; EDGAR was unreachable from our build environment"], { x: 0.8, y: 4.0, w: 11.8, h: 2.6, fontSize: 16 });
s.addNotes("Be upfront that the benchmark is synthetic and why. Seeded cases: over-cap, not-permitted add-back, arithmetic error, restatement, statement/certificate conflict, stale threshold, missing page, undatable amendment, unit change, two injections, tight, breach.");

// 10 status chart
s = slide("CONTENT", "Evaluation");
T(s, "Every breach found, every unsafe case stopped");
s.addChart(pres.charts.BAR, [
  { name: "Breaches detected (of 4)", labels: ["This system", "Stale-definitions spreadsheet", "Trust borrower certificate"], values: [S.system.detected, S.baseline_stale_spreadsheet.detected, S.baseline_certificate_trust.detected] },
  { name: "False breaches", labels: ["This system", "Stale-definitions spreadsheet", "Trust borrower certificate"], values: [S.system.false_breach, S.baseline_stale_spreadsheet.false_breach, S.baseline_certificate_trust.false_breach] },
  { name: "Should-halt cases reported compliant (of 4)", labels: ["This system", "Stale-definitions spreadsheet", "Trust borrower certificate"], values: [S.system.halt_cases_reported_as_compliant, S.baseline_stale_spreadsheet.halt_cases_reported_as_compliant, S.baseline_certificate_trust.halt_cases_reported_as_compliant] },
], { x: 0.6, y: 1.4, w: 7.8, h: 5.2, barDir: "col", barGapWidthPct: 60, chartColors: [HEX.accent1, HEX.accent3, HEX.accent4],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 12, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt",
  showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt",
  catAxisLabelColor: HEX.accent5, valAxisLabelColor: HEX.accent5, valAxisLabelFontSize: 11, valAxisMaxVal: 4, valAxisMajorUnit: 1,
  valGridLine: { color: "E3E8EF", size: 0.5 }, catGridLine: { style: "none" }, objectName: "statusChart" });
card(s, 8.8, 1.4, 3.9, 5.2);
stat(s, 9.1, 1.6, 3.4, `${S.system.exact_status_match}/32`, "exact status match (spreadsheet " + S.baseline_stale_spreadsheet.exact_status_match + ", certificate " + S.baseline_certificate_trust.exact_status_match + ")");
stat(s, 9.1, 3.6, 3.4, `${M.discrepancy.cause_exact}/${M.discrepancy.seeded}`, "seeded certificate gaps given the correct cause; 0 on clean quarters", C.accent2);
s.addNotes("The spreadsheet misses both Apex breaches because it uses the pre-amendment threshold and takes add-backs at face value. Trusting the certificate misses the three breaches the borrowers concealed. Neither baseline can halt, so a missing page or an undatable amendment comes out as compliant.");

// 11 retrieval
s = slide("CONTENT", "Evaluation");
T(s, "Graph + date rule beats chunk retrieval on amendments");
s.addChart(pres.charts.BAR, [
  { name: "Knowledge graph + effective-date rule", labels: ["Governing threshold", "Add-back cap", "All 47 questions"], values: [100, 100, 100] },
  { name: "Chunk retrieval (TF-IDF top-3)", labels: ["Governing threshold", "Add-back cap", "All 47 questions"],
    values: [M.retrieval.chunk_tfidf_top3.governing_threshold.answer_accuracy, M.retrieval.chunk_tfidf_top3.addback_cap.answer_accuracy, M.retrieval.chunk_tfidf_top3.all.answer_accuracy].map((v) => Math.round(v * 100)) },
], { x: 0.6, y: 1.4, w: 7.8, h: 5.2, barDir: "col", barGapWidthPct: 60, chartColors: [HEX.accent1, HEX.accent3],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 12, dataLabelColor: HEX.dk1, dataLabelFormatCode: '0"%"', dataLabelFontFace: "+mn-lt",
  showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt",
  catAxisLabelColor: HEX.accent5, valAxisLabelColor: HEX.accent5, valAxisLabelFontSize: 11, valAxisMaxVal: 100, valAxisMajorUnit: 25,
  valGridLine: { color: "E3E8EF", size: 0.5 }, catGridLine: { style: "none" }, objectName: "retrievalChart" });
card(s, 8.8, 1.4, 3.9, 5.2);
tx(s, "Typical chunk failure", { x: 9.05, y: 1.6, w: 3.4, h: 0.4, fontSize: 16, bold: true });
tx(s, "Apex, any quarter after the First Amendment. Top chunks: the ratio definition, the original covenant (4.50x) and the amendment preamble. The clause that sets 4.25x never appears.",
  { x: 9.05, y: 2.1, w: 3.4, h: 2.4, fontSize: 15 });
tx(s, "This is the multi-hop failure KG-MuLQA documents, now on our own covenant questions.", { x: 9.05, y: 4.7, w: 3.4, h: 1.4, fontSize: 14, italic: true, color: C.accent2 });
s.addNotes(`Chunk retrieval: ${Math.round(M.retrieval.chunk_tfidf_top3.all.answer_accuracy * 100)}% answer accuracy and full evidence on ${Math.round(M.retrieval.chunk_tfidf_top3.all.full_evidence_rate * 100)}% of questions. The graph gets all sections every time. Caveat: an LLM reader on top of chunks might do better; that is what the single-prompt baseline will test.`);

// 12 controls
s = slide("CONTENT", "Evaluation");
T(s, "Controls held on every attack and failure we seeded");
table(s, [["Test", "Result"],
  ["Instruction hidden in certificate text", "Pass: BREACH, 4.40x, identical to the clean twin"],
  ["Instruction inside a numeric field", "Pass: value left empty, run halts for the analyst"],
  ["Missing certificate page", "Pass: halt, no status"], ["Amendment with no effective date (2 quarters)", "Pass: halt, no threshold chosen"],
  ["Unit change on one statement page", "Pass: XBRL tie-out fails, whole page re-read, 5 values pending"],
  ["Restatement · conflict · stale threshold", "Pass: flagged with the correct cause"],
  [`Fabricated number added to each memo`, `${M.memo_guard.adversarial_insertions_blocked}/${M.memo_guard.drafts} drafts blocked`],
  ["Edited audit entry", "Hash chain breaks at that entry"]], { x: 0.6, y: 1.45, w: 8.2, colW: [3.8, 4.4], fontSize: 15, rowH: 0.55 });
card(s, 9.2, 1.45, 3.5, 4.9);
tx(s, "Why it holds", { x: 9.45, y: 1.6, w: 3.0, h: 0.4, fontSize: 16, bold: true });
tx(s, "The investigator never receives document text. It sees typed numbers and citations only, and its tools cannot write. The control does not depend on detecting the attack (CaMeL-style separation).",
  { x: 9.45, y: 2.1, w: 3.05, h: 4.0, fontSize: 15 });
s.addNotes("Tie to AgentDojo and CaMeL. The heuristic 'instruction-like text' flag is only advisory for the analyst; it is not the control.");

// 13 early warning + tolerance
s = slide("CONTENT", "Evaluation");
T(s, "Early warning and tolerance: useful, but not precise");
img(s, "headroom_trend.png", 0.6, 1.3, 7.3);
bullets(s, ["All 4 breaches were flagged 1-2 quarters earlier", "But 16 of 28 quarters carry a flag: a watch signal for a PM, not a prediction",
  "Tolerance: a very tight setting turned rounding into 10 needless investigations; the default separated real gaps from rounding",
  `24 of 32 packages needed only a sign-off (about ${Math.round(M.workload.fields_rekeyed_manually_per_package_baseline)} fields re-keyed per package today)`],
  { x: 8.2, y: 1.45, w: 4.6, h: 5.2, fontSize: 15 });
s.addNotes("We removed forward projection after the midpoint feedback. Early warning uses headroom trend and breach sensitivity on reported figures only. Be honest about the false-alarm rate. We did not time analysts; docs/timing_protocol.md has the crossover test.");

// real filings
s = slide("CONTENT", "Evaluation");
T(s, "Real SEC filings: the hard cases are real");
const rf = [["4 of 7", "thresholds change on an event or election, not a date", "Enviri: \u201cfrom and after the closing of the Rail Disposition\u201d \u2192 \u22120.25x; DSG: \u201cCovenant Ratchet Date\u201d; ModivCare: \u201cCovenant Relief Period\u201d", C.accent4],
  ["2 of 7", "conformed copies with redline artifacts", "DSG interest coverage reads \u201c2.75 2.00 to 1.00\u201d; ModivCare \u201c5:25 5.25 to 1:00 1.00\u201d", C.accent3],
  ["3 of 9", "clauses found by a fixed pattern", "Templated parsing does not transfer; real text goes to the LLM graph builder plus team review", C.accent1]];
rf.forEach(([big, lab, ex, col], i) => {
  const x = 0.6 + i * 4.15;
  card(s, x, 1.45, 3.95, 4.6);
  stat(s, x + 0.3, 1.6, 3.4, big, lab, col);
  tx(s, ex, { x: x + 0.3, y: 3.6, w: 3.4, h: 2.3, fontSize: 14 });
});
tx(s, "10 filers pulled from EDGAR (~170 credit documents + XBRL); covenants read for 9. Draft labels, pending team verification (data_real/).",
  { x: 0.6, y: 6.25, w: 12.1, h: 0.5, fontSize: 13, italic: true, color: C.accent5 });
s.addNotes("This is why the effective-date rule halts on event-dependent thresholds: in real agreements it is the common case, not an edge case. Our synthetic Cedar borrower models exactly this. The counts are from our reading of the filings and still need a teammate to verify.");

// 14 implementation
s = slide("CONTENT", "Implementation");
T(s, "Path to production: shadow first, authority last");
[["0", "Real-filing pilot", "10-20 EDGAR borrowers · LLM graph builder + full review · LLM extractor · single-prompt baseline · timed analysts"],
 ["1", "Shadow mode", "1-2 quarters alongside analysts; outputs unused; tune tolerances and halt rates"],
 ["2", "Assisted production", "Humans sign; independent validation of extractor and graph builder (SR 11-7 principles)"],
 ["3", "Portfolio scale", "Full book; rating analytics; precedent search over the lender's own waiver memos"]].forEach(([k, h, d], i) => {
  const x = 0.6 + i * 3.1;
  card(s, x, 1.5, 2.9, 3.4);
  s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: 1.7, w: 0.6, h: 0.6, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: `o${++n}` });
  tx(s, k, { x: x + 0.25, y: 1.7, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0 });
  tx(s, h, { x: x + 0.25, y: 2.45, w: 2.5, h: 0.5, fontSize: 17, bold: true });
  tx(s, d, { x: x + 0.25, y: 3.0, w: 2.5, h: 2.0, fontSize: 14 });
});
tx(s, "Regulatory fit (not legal advice): reproducibility, named accountability and change control serve model-risk principles (SR 11-7), fund valuation (Rule 2a-5) and books-and-records duties. The hash-chained log provides them by construction.",
  { x: 0.6, y: 5.4, w: 12.1, h: 1.0, fontSize: 15, color: C.accent5 });
s.addNotes("Integration points: data room / email intake, document repository, monitoring tracker, rating system, fund valuation. At scale, the binding cost is graph review for new agreements and amendments, not compute.");

// 15 limitations
s = slide("CONTENT", "Close");
T(s, "What this does not show yet");
const lim = [["Synthetic, templated documents", "Extraction and graph scores are near-perfect by construction and will fall on real filings"],
  ["LLM backends unevaluated", "Claude extractor, graph builder, investigator and single-prompt baseline are coded and switch on with an API key"],
  ["No analyst timing", "We count decisions, not minutes; the timing protocol is ready"],
  ["Small sample", "4 borrowers, 32 quarters: per-case evidence, not rates"],
  ["Closed set of causes", "A novel cause returns as unresolved, which is safe but needs a person"],
  ["Proxy agreements", "Public agreements are mostly bank-led syndicated deals"]];
lim.forEach(([h, d], i) => {
  const x = 0.6 + (i % 2) * 6.15, y = 1.45 + Math.floor(i / 2) * 1.7;
  card(s, x, y, 5.95, 1.5);
  tx(s, h, { x: x + 0.25, y: y + 0.12, w: 5.5, h: 0.45, fontSize: 17, bold: true });
  tx(s, d, { x: x + 0.25, y: y + 0.6, w: 5.5, h: 0.85, fontSize: 14 });
});
s.addNotes("Say this plainly. The control evidence does not depend on realistic data; the accuracy evidence does.");

// takeaways
s = slide("CONTENT", "Close");
T(s, "Three takeaways");
[["Put the definitions in a graph and pick the version by date", "Most errors hide in amended definitions; chunk retrieval returned the superseded threshold"],
 ["Let models propose, never decide", "Every number comes from code, every status from a rule, every determination from a named person"],
 ["Stopping is a feature", "Missing pages, undatable amendments and injected text halt the run instead of producing a confident wrong answer"]].forEach(([h, d], i) => {
  const y = 1.55 + i * 1.65;
  s.addShape(pres.shapes.OVAL, { x: 0.7, y: y + 0.15, w: 0.75, h: 0.75, fill: { color: C.accent2 }, line: { color: C.accent2 }, objectName: `o${++n}` });
  tx(s, String(i + 1), { x: 0.7, y: y + 0.15, w: 0.75, h: 0.75, fontSize: 22, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0 });
  tx(s, h, { x: 1.75, y, w: 10.8, h: 0.6, fontSize: 22, bold: true });
  tx(s, d, { x: 1.75, y: y + 0.6, w: 10.8, h: 0.7, fontSize: 16, color: C.accent5 });
});
s.addNotes("Close on the three ideas. Then hand to Q&A.");

// 16 close
s = slide("DARK_TITLE", "Close");
T(s, "Questions");
s.addText([{ text: "Code, data, tests and evaluation: github.com/vidss04/covenant-monitoring", options: { breakLine: true } },
  { text: "make test · make eval · make demo · make app", options: { fontSize: 14 } }], { placeholder: "body" });
s.addNotes("Likely questions: why not let the LLM compute (it cannot be validated like code); how the graph is reviewed at scale (review only changed sections); what happens on an equity cure (recorded, not simulated yet).");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
