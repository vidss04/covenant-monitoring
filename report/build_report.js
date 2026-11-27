// Builds report/MGT8803_Final_Report_Covenant_Monitoring.docx   (node report/build_report.js)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, HeadingLevel, LevelFormat, PageBreak, Footer, PageNumber, BorderStyle, TableOfContents,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const FIG = (f) => path.join(ROOT, "results", "figures", f);
const M = JSON.parse(fs.readFileSync(path.join(ROOT, "results", "metrics.json")));
const AIH = JSON.parse(fs.readFileSync("/tmp/aih.json"));
const CASES = JSON.parse(fs.readFileSync("/tmp/caserows.json"));
const FONT = "Arial";
const W = 9360; // content width (US Letter, 1" margins)

// ---------- helpers
function runs(text, opts = {}) {
  // **bold** markup
  const out = [];
  text.split(/(\*\*[^*]+\*\*)/).forEach((t) => {
    if (!t) return;
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, font: FONT, ...opts }));
    else out.push(new TextRun({ text: t, font: FONT, ...opts }));
  });
  return out;
}
const P = (t, o = {}) => new Paragraph({ children: runs(t, o.run || {}), spacing: { after: 120, line: 276 }, alignment: o.align, ...o.p });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT })] });
const B = (t, lvl = 0) => new Paragraph({ numbering: { reference: "bul", level: lvl }, children: runs(t), spacing: { after: 60, line: 264 } });
const N = (t) => new Paragraph({ numbering: { reference: "num", level: 0 }, children: runs(t), spacing: { after: 60, line: 264 } });
const CAP = (t) => new Paragraph({ children: runs(t, { size: 18, italics: true, color: "555555" }), spacing: { before: 40, after: 200 } });
const MONO = (t) => t.split("\n").map((ln) => new Paragraph({ children: [new TextRun({ text: ln || " ", font: "Courier New", size: 15 })], spacing: { after: 0, line: 220 } }));

function fig(file, widthIn, caption) {
  const buf = fs.readFileSync(FIG(file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  const px = widthIn * 96;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 0 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: px, height: Math.round((px * h) / w) },
        altText: { title: caption, description: caption, name: file } })] }),
    CAP(caption),
  ];
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(headers, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const sz = opts.size || 18;
  const cell = (t, i, head, shade) => new TableCell({
    borders, width: { size: widths[i], type: WidthType.DXA },
    shading: head ? { fill: "1F3A5F", type: ShadingType.CLEAR, color: "auto" } : (shade ? { fill: "F3F6FA", type: ShadingType.CLEAR, color: "auto" } : undefined),
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: String(t).split("\n").map((ln) => new Paragraph({ spacing: { after: 0, line: 240 },
      children: head ? [new TextRun({ text: ln, bold: true, color: "FFFFFF", font: FONT, size: sz })] : runs(ln, { size: sz }) })),
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true)) }),
      ...rows.map((r, j) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, i, false, j % 2 === 1)) }))],
  });
}
const SP = () => new Paragraph({ children: [], spacing: { after: 80 } });
const pct = (x) => `${Math.round(x * 1000) / 10}%`;
const S = M.status;

// ---------- content
const C = [];
// Title block
C.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 60 }, children: [new TextRun({ text: "MGT 8803 AI in Finance · Final Project Report", font: FONT, size: 20, color: "555555" })] }));
C.push(new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: "Governed Agentic Covenant Monitoring for a Middle-Market Direct Lender", font: FONT, size: 36, bold: true, color: "1F3A5F" })] }));
C.push(P("Track 1: Lending and Private Credit · Quarterly covenant compliance and early-warning monitoring", { run: { size: 22, color: "333333" } }));
C.push(P("Vivan Jain · Srivant Vishnuvajjala · Vidhi Chaturvedi · Manasi Prasad", { run: { size: 22 } }));
C.push(P("Code and data: github.com/vidss04/covenant-monitoring · All borrower data in this report is synthetic and labelled as such.", { run: { size: 18, color: "555555" } }));
C.push(new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: "1F3A5F", space: 4 } }, children: [], spacing: { after: 160 } }));

// 1
C.push(H1("1. Executive Summary"));
C.push(P("**Problem.** After a loan closes, a direct lender re-tests each borrower's financial covenants every quarter. An analyst re-keys PDF financials, re-reads an amended credit agreement to rebuild a negotiated EBITDA definition, recomputes the ratios in a spreadsheet and reconciles them to the borrower's own compliance certificate. The work is repetitive, the definitions drift as amendments accumulate, the link from a ratio back to its clause and page is weak, and the consequential calls (declaring a breach, waiving it, changing a risk rating) belong to named people under a delegation of authority."));
C.push(P("**Redesign.** We split the cycle by what each step needs. Models may only propose: typed, page-cited extractions; a knowledge graph of the agreement; a closed-set explanation of why the borrower's certificate disagrees with ours; and memo prose. Deterministic code resolves which amendment governs each quarter by effective date, applies add-back caps, computes every ratio, headroom and sensitivity, and checks figures against independent evidence (XBRL, the borrower's own statements, prior packages). Only people accept findings, sign determinations, declare breaches or talk to the borrower, and an append-only, hash-chained log records each step."));
C.push(P(`**Prototype and results.** The prototype runs the full cycle on 32 borrower-quarters (4 synthetic borrowers, 8 test periods, 13 seeded case types) built to mirror EDGAR credit-agreement structure, with an answer key computed independently before any run. It matched the expected outcome in **${S.system.exact_status_match}/32** periods, detected **4/4** breaches with no false breaches, and halted on all 4 cases where no status should be issued. A spreadsheet using a definitions summary from closing matched ${S.baseline_stale_spreadsheet.exact_status_match}/32 and missed 2 breaches; trusting the certificate matched ${S.baseline_certificate_trust.exact_status_match}/32 and missed 3. Graph-based definition retrieval answered 47/47 multi-hop questions against ${pct(M.retrieval.chunk_tfidf_top3.all.answer_accuracy)} for chunk retrieval, which mostly returned the superseded threshold. All ${M.discrepancy.seeded} seeded certificate discrepancies were detected and correctly classified. Both prompt-injection tests and all ${M.failure_tests.length} failure tests passed, and 24 of 32 packages needed only a sign-off.`));
C.push(P("**Most important limitation and control.** The benchmark is synthetic and the agreement language is templated, so the extraction and graph-parsing scores are near-perfect by construction and do not predict performance on real filings. The LLM backends are implemented but were not evaluated (no API access in our build environment), and we did not time analysts. What the evidence does support is the control design: no model output can set a status or a number, every seeded failure was stopped or flagged, and the system refuses to choose a threshold when an amendment's effective date is undeterminable."));

// 2
C.push(H1("2. Industry and Use-Case Context"));
C.push(P("Middle-market direct lenders (private credit funds, BDCs and their managers) typically hold loans with maintenance financial covenants: a maximum leverage ratio and a minimum interest or fixed-charge coverage ratio, tested every quarter on a trailing four-quarter basis. The credit agreement obliges the borrower to deliver financial statements and an officer-signed compliance certificate within a fixed window (commonly 45 days after quarter end), and failure to deliver or to comply is an Event of Default, usually subject to an equity-cure right."));
C.push(P("Covenant monitoring is where a lender first learns that a credit is deteriorating, so it drives watchlists, risk ratings, valuation marks for fund reporting, and the negotiation of waivers and amendments. The economic stakes sit in the definitions. Consolidated EBITDA is negotiated deal by deal and includes add-backs (non-recurring charges, pro forma cost savings, run-rate synergies) that are often capped as a percentage of EBITDA, and amendments reset thresholds or rewrite definitions partway through the loan. A borrower that claims an uncapped add-back or applies a superseded threshold can certify compliance while in breach."));
C.push(table(["Stakeholder", "Interest in the workflow", "Effect of the redesign"], [
  ["Credit / portfolio analyst", "Accurate, defensible recomputation each quarter", "Re-keying and definition rebuilding replaced by reviewing cited findings; becomes a reviewer"],
  ["Portfolio manager / deal lead", "Early warning; watchlist and rating calls", "Headroom trend and sensitivity every quarter; signs non-breach determinations"],
  ["Credit committee", "Authority over breach, waiver, amendment, cure", "Receives a memo where every number traces to a page and clause; authority unchanged"],
  ["Borrower CFO", "Timely, fair treatment of the certificate", "No automated communication; disputes reference specific clauses and pages"],
  ["Compliance, internal audit, model risk", "Evidence, reproducibility, separation of duties", "Hash-chained log, versioned engine, config-held tolerances and authority matrix"],
  ["Fund investors, auditors, regulators", "Valuation and disclosure rest on accurate monitoring", "Determinations are reproducible from the log alone"],
], [2300, 3300, 3760]));
C.push(CAP("Table 1. Stakeholders and how the redesign affects them."));

// 3
C.push(H1("3. Current-State Workflow and Pain Points"));
C.push(P("We built the current-state map from public documents (the reporting covenants, compliance-certificate exhibits and definitions sections of credit agreements filed on SEC EDGAR) and from the course references. The internal review chain is not visible in filings, so it is an assumption, and we label it as one."));
C.push(...fig("current_state.png", 6.4, "Figure 1. Current-state quarterly cycle and where the pain points occur."));
C.push(table(["Step", "Role", "Systems / documents", "Decision or control", "Common exceptions"], [
  ["Delivery and intake", "Borrower CFO; portfolio ops", "Email / data room; reporting calendar", "Contractual deadline; officer certification", "Late or partial package"],
  ["Spreading", "Analyst", "PDF statements -> Excel or spreading tool", "None beyond analyst care", "Restated prior periods; unit changes"],
  ["Covenant recomputation", "Analyst", "Credit agreement + amendments; spreadsheet", "Independent recomputation vs certificate", "Disputed add-backs; borrower arithmetic; stale threshold"],
  ["Determination and review", "Analyst; PM", "Monitoring tracker", "Second review by PM; watchlist / rating", "Tight headroom judgment"],
  ["Escalation and approval", "Credit committee; counsel", "Memo; delegation matrix; minutes", "Authority matrix; committee minutes", "Waiver, amendment, equity cure, covenant reset"],
  ["Recording", "Analyst", "Document repository; tracker", "Filing", "Evidence scattered across email and spreadsheets"],
], [1500, 1350, 2150, 2260, 2100], { size: 17 }));
C.push(CAP("Table 2. Current-state steps, roles, systems, controls and exceptions."));
C.push(table(["#", "Pain point", "Why it matters", "Addressed by"], [
  ["P1", "Financials re-keyed by hand from PDFs", "Time each quarter; transcription errors propagate into ratios", "Typed extraction with page cites + XBRL tie-out + second independent read"],
  ["P2", "EBITDA definition rebuilt from an amended agreement, or from a summary that goes stale", "A superseded threshold or cap silently changes the answer (our stale-spreadsheet baseline missed 2 of 4 breaches)", "Knowledge graph + deterministic effective-date rule"],
  ["P3", "Weak link from a ratio to its source page and governing clause", "The link matters most when a breach is contested", "Every field and term carries doc/section/page; audit log"],
  ["P4", "Monitoring is reactive", "Deterioration is noticed when the certificate arrives", "Headroom trend + breach sensitivity each quarter"],
  ["P5", "Add-back judgment varies by analyst", "Inconsistent treatment across the portfolio", "Caps applied by rule; disputed items go to a named reviewer"],
  ["P6", "All inputs come from the borrower and are untrusted", "Certificate text can be wrong, self-serving or adversarial", "Free text never reaches the engine or agent; anomalies halt"],
  ["P7", "Controls occur late (at PM review)", "Errors are caught after work is done, if at all", "Verification runs before any status is computed"],
], [450, 2500, 3150, 3260], { size: 17 }));
C.push(CAP("Table 3. Pain points, inferred from documents and public process descriptions rather than observed at an institution."));

// 4
C.push(H1("4. Future-State Workflow"));
C.push(P("The guiding question for each task was the least powerful tool that does the job reliably. Wherever the answer is contractual arithmetic or a date comparison, it is code. Models appear only where the input is unstructured and the output can be checked."));
C.push(table(["Task", "Approach", "Why this and not something else", "Authority"], [
  ["Delivery deadline tracking", "Deterministic rule", "Date arithmetic from the agreement; late delivery is itself a default trigger", "System flags; PM decides"],
  ["Statement / certificate extraction", "Two deterministic extractors (offline); LLM extractor for real layouts, typed schema", "Layouts vary in practice; a strict validator bounds what any extractor may emit", "Proposes values"],
  ["Agreement -> knowledge graph", "Rule parser (templated text) or LLM into fixed node/edge schema, then team review", "Definitions are multi-hop and spread across sections and amendments", "Proposes graph; team approves"],
  ["Which version governs a quarter", "Deterministic: latest effective date <= test-period end; halt if undeterminable", "A retriever can return the wrong version; this is a date comparison, not a judgment", "Rule; PM releases halts"],
  ["Definition retrieval", "Graph traversal; clause text shown to the analyst", "Chunk retrieval returned the superseded threshold in our test (Section 8)", "Read-only"],
  ["Covenant math, caps, headroom, sensitivity", "Deterministic engine, one function per covenant type, versioned", "Must be exact and reproducible", "Computes provisional status"],
  ["Verification", "Rules vs independent evidence: XBRL, statements, prior package, arithmetic, threshold", "Separation of duties needs a different evidence source, not another LLM", "Flags; may halt"],
  ["Discrepancy investigation", "Bounded ReAct loop over read-only tools; closed-set causes; rule or LLM policy", "The next check depends on the last result; output is checkable and non-authoritative", "Proposes causes"],
  ["Early warning", "Deterministic headroom trend + breach sensitivity on reported figures", "Forward projection dropped after midpoint: needs forecasts public data cannot support", "Flags; PM decides watchlist"],
  ["Draft memo", "Template with engine-filled slots; optional LLM prose; numeric guard", "The model cannot introduce a number", "Draft only"],
  ["Accept findings / re-read values", "Human (analyst)", "Judgment on borrower disputes", "Analyst"],
  ["Sign determination; rating", "Human (PM); breach requires credit committee", "Written delegation of authority", "PM / committee"],
  ["Waiver, amendment, equity cure; borrower communication", "Human (committee, counsel, deal team)", "Legal and relationship consequences", "Out of system"],
], [1850, 2600, 2900, 2010], { size: 16 }));
C.push(CAP("Table 4. Technology choice for every major task."));
C.push(P("**What we deliberately did not use.** Mathematical optimisation has no role in this workflow: compliance is a test against a contract, not a choice among feasible options. The one place it could appear (structuring a waiver or reset) is a negotiation that belongs to people. Traditional ML is also left out of the first release. We have no labelled default history, and a learned early-warning score would be harder to defend than a sensitivity the analyst can recompute by hand. Section 10 lists where both could be added later."));

// 5
C.push(H1("5. Technical Architecture and Data"));
C.push(...fig("future_state.png", 6.4, "Figure 2. Future-state architecture. Colour shows the source of each output; the dashed line separates proposal and computation from authority."));
C.push(table(["Component", "Implementation", "Key design point"], [
  ["Extraction", "cov/extract.py: pdfplumber (pass 1, document-level units) and PyMuPDF (pass 2, page-level units); cov/extract_llm.py (Claude, forced JSON schema)", "Free text in a numeric slot becomes an anomaly with an empty value; never guessed"],
  ["Knowledge graph", "cov/kg.py (NetworkX): covenant, threshold, defined term, add-back, cap, netting, amendment nodes; has_threshold / uses / permits / capped_by / sets / adds edges; cov/kg_llm.py for real agreements", "Every node carries doc, section, page"],
  ["Governing version", "resolve_terms(): base schedule, then amendments in effective-date order; halt if executed but undated", "Reasons and evidence recorded per quarter"],
  ["Engine", "cov/engine.py: add-back caps, leverage (total / secured, capped / uncapped cash netting), ICR, FCCR, headroom, sensitivity, early warning", "Engine version + git commit in every record"],
  ["Verification", "cov/verify.py: XBRL tie-out (0.5%), period consistency, statement vs certificate, certificate arithmetic, threshold check, deadline", "Tolerances in config/settings.json, never in a prompt"],
  ["Investigator", "cov/agent.py Toolbox (8 read-only tools + submit); RuleInvestigator; cov/agent_llm.py ClaudeInvestigator", "12-step budget; closed set of 7 causes"],
  ["Memo, approval, audit", "cov/memo.py numeric guard; cov/approval.py role matrix and separation of duties; cov/audit.py SHA-256 chain", "System holds no role"],
  ["Interfaces", "app/approval_app.py (Streamlit); demo.py (terminal); eval/ harness", "Free text and page images shown only to people"],
], [1600, 4900, 2860], { size: 16 }));
C.push(CAP("Table 5. System components."));
C.push(P("**Data.** All inputs in this version are synthetic and labelled in every document. Four fictional borrowers have credit agreements and amendments written in EDGAR Exhibit-10 structure (definitions, financial covenants, add-back caps, step-downs, an Exhibit D certificate), with boilerplate sections that contain distractor ratios (pricing grid, excess-cash-flow sweep, incremental incurrence test). Each test period has a three-page financial package (quarterly income statement with an LTM build, balance sheet, cash-flow supplement) and a three-page certificate, both rendered to PDF so extraction faces a layout problem. XBRL-style company facts carry as-filed and restated values. The covenant designs differ on purpose: total vs senior-secured leverage, capped, uncapped and no cash netting, ICR vs FCCR, a base-agreement step-down schedule, threshold resets, a new add-back permitted by amendment, and an amendment whose effective date depends on an acquisition closing (Appendix E)."));
C.push(P("**Why synthetic, and how real data plugs in.** EDGAR was not reachable from our build environment, and negotiated add-backs and borrower certificates are never public in any case. The proposal and midpoint planned real agreements and financials with synthetic certificates; this version makes the whole benchmark synthetic so that every quarter has a known answer. scripts/fetch_edgar.py retrieves Exhibit 10 credit documents and XBRL company facts, and the LLM graph builder and extractor take real text through the same schema. Real filings are the first next step (Section 10)."));
C.push(P("**Implementation assumptions.** The lender holds the loan directly (a syndicated deal would add required-lender votes); figures are in USD thousands; tests are trailing four quarters; packages arrive in chronological order so the prior package is available for restatement checks."));

// 6
C.push(H1("6. Authority and Governance"));
C.push(P("The design follows a Generate -> Verify -> Constrain -> Decide -> Gate -> Act/Record sequence. Reasoning and tool use never imply authority. The table answers the assignment's eight questions for the consequential step, which is issuing a compliance determination."));
C.push(table(["Question", "Answer in this system"], [
  ["1. What can the LLM generate or propose?", "Typed field values with page references; graph nodes and edges; a closed-set cause per discrepancy with citations; memo prose with no numbers of its own."],
  ["2. What is independently verified?", "GAAP line items against XBRL; any page that fails tie-out is re-read by a second extractor using a different library and unit logic; overlapping quarters against the prior package; certificate arithmetic; certificate debt/interest/EBITDA against statements; certificate threshold against the resolved terms. Add-backs and certificate-only figures have no public cross-check and are logged as page-tied, not independently verified."],
  ["3. Which hard rules decide feasibility?", "The governing version is the latest effective date on or before the test-period end; add-back caps and permitted-item lists; cash-netting caps; debt basis; covenant thresholds. Missing required fields, numeric anomalies, failed tie-out on both reads, or an undatable amendment halt the run."],
  ["4. If several options are feasible, how is one chosen?", "There is one contractual answer per quarter. Where the inputs conflict (statement vs certificate; pass 1 vs pass 2), the system recommends the value backed by independent evidence and a named analyst accepts or rejects it."],
  ["5. Who has authority?", "Analyst: accept or reject findings and re-read values. Portfolio manager: sign COMPLIANT or TIGHT, release halts, change ratings. Credit committee: declare breach, approve waiver, amendment or cure. Matrix in config/settings.json, enforced in cov/approval.py."],
  ["6. What runs automatically?", "Extraction, graph construction, version resolution, verification, engine, investigation, draft memo, logging. None of these can record a determination or contact the borrower."],
  ["7. Verification fails, data missing, or exception needed?", "Halt with stated reasons and no status; unexplained gaps are marked unresolved; overriding the engine status requires a written rationale; policy exceptions (waivers) go to committee outside the system."],
  ["8. What is logged?", "Per run: input file hashes, code commit, engine version, governing terms with reasons and evidence, every field with page and verification state, tolerances, re-reads, the full agent trace, memo and guard result. Per decision: user, role, timestamp, rationale. Entries are hash-chained, so editing one breaks verification."],
], [2700, 6660], { size: 17 }));
C.push(CAP("Table 6. Authority and governance for the compliance determination."));
C.push(P("**Separation of duties reflects different evidence, not more model calls.** The investigator proposes from typed data; verification uses XBRL, the borrower's own statements and prior packages; the engine applies the contract; and the approval gate checks identity and role. The gate also enforces that whoever reviewed the findings for a run cannot sign its determination, that a breach can only be declared by the credit committee, and that no determination can be signed while findings or re-read values are open."));
C.push(P("**Untrusted input (CaMeL-style separation).** Borrower content reaches four channels. The extractor sees full text but can only emit typed values. The graph builder sees agreement text and emits typed nodes. The investigator sees only typed fields and citations, and its tool choice is driven by the engine's component list. The analyst screen is the only place free text and page images appear, and they are shown to a person. A heuristic flag on instruction-like text is advisory only; the control does not depend on detecting the attack."));

// 7
C.push(H1("7. Prototype"));
C.push(P("The repository implements the full redesigned cycle from package intake to a signed, logged determination. The rule backends run offline and are fully reproducible; the Claude backends (extractor, graph builder, ReAct investigator, single-prompt baseline) use the same interfaces and switch on with an API key. The test suite has 45 unit tests, including the engine against all 32 answer-key rows, version resolution for every quarter, the authority gate, and audit-chain tamper detection."));
C.push(P("**Walk-through: Apex Industrial, quarter ending 30 September 2025 (the worked case from our midpoint).** The certificate reports 4.08x against 4.50x and certifies compliance. The graph shows that the First Amendment, effective 30 June 2025, replaced 4.50x with 4.25x, so the base and amended versions both apply. The 15% cap on non-recurring charges and pro forma savings limits $9.0m of claimed add-backs to $6.0m, which gives Consolidated EBITDA of $46.0m and leverage of 4.35x: a breach by 0.10x. The gap exceeds tolerance, so the investigator runs three read-only tool calls and proposes addback_over_cap citing Section 1.01(c) and certificate page 2. A threshold flag notes that the certificate applied the superseded 4.50x. The memo states the sensitivity ($1.06m more EBITDA or $4.5m less net debt to comply), and the early-warning flag had already fired in the prior quarter. In the demo, the PM's attempt to sign the breach is refused, the analyst accepts the finding, the same analyst's attempt to sign as committee is refused, and a committee member signs (Appendix B)."));
C.push(table(["Demo scene", "Future-state steps shown", "Control demonstrated"], [
  ["1. Apex Q3 2025 breach", "Graph -> version rule -> engine -> investigator -> memo", "Model never produces a number; citations to clause and page"],
  ["2. Who may sign", "Approval gate", "Role matrix, open-item check, separation of duties"],
  ["3. Apex Q4 2025 injected instruction", "Extraction -> analyst screen", "Instruction never reaches engine or agent; status identical to clean twin"],
  ["4. Cedar Q2 2026 undatable amendment", "Version rule -> halt", "System refuses to choose a threshold"],
  ["5. Streamlit screen", "Analyst review, page image, sign, audit trail", "Human decisions recorded with user, role and time"],
], [2600, 3500, 3260], { size: 17 }));
C.push(CAP("Table 7. Live-demo scenes mapped to the future-state workflow (script in docs/demo_script.md)."));

// 8
C.push(H1("8. Evaluation and Results"));
C.push(H2("8.1 Design"));
C.push(P("The benchmark has 32 borrower-quarters: 15 clean, plus seeded tight-headroom, breach, add-back-over-cap, add-back-not-permitted, borrower-arithmetic, restatement, statement-vs-certificate conflict, stale threshold, missing certificate page, undatable amendment, unit change on one statement page, and two prompt-injection variants. Two borrowers present EBITDA rounded to $100k to add realistic noise. The answer key, extraction gold, graph gold and 47 retrieval questions were produced before any pipeline run, and the answer key is computed by separate code from the engine. Every system metric is computed from the audit log. No metric asks a model to grade a model."));
C.push(P("**Baselines.** (B1) **Trust the certificate:** take the borrower's certified status. (B2) **Stale-definitions spreadsheet:** recompute from the statements with the add-backs as claimed and the threshold from the original agreement, which is the definitions summary that goes stale (pain point P2). (B3) **Single-prompt LLM:** coded in eval/llm_baseline.py but not run, because the build environment had no API access. (B4) **Chunk retrieval:** TF-IDF over agreement sections, top-3, answer read from the first chunk with a value, standing in for plain chunk RAG without an LLM reader."));
C.push(H2("8.2 Compliance status"));
C.push(table(["Metric (32 test periods)", "This system", "B2 stale spreadsheet", "B1 trust certificate"], [
  ["Exact match to expected outcome", `${S.system.exact_status_match}`, `${S.baseline_stale_spreadsheet.exact_status_match}`, `${S.baseline_certificate_trust.exact_status_match}`],
  ["Breaches detected (of 4)", `${S.system.detected}`, `${S.baseline_stale_spreadsheet.detected}`, `${S.baseline_certificate_trust.detected}`],
  ["False breaches", `${S.system.false_breach}`, `${S.baseline_stale_spreadsheet.false_breach}`, `${S.baseline_certificate_trust.false_breach}`],
  ["Should-halt cases issued a compliant status (of 4)", `${S.system.halt_cases_reported_as_compliant}`, `${S.baseline_stale_spreadsheet.halt_cases_reported_as_compliant}`, `${S.baseline_certificate_trust.halt_cases_reported_as_compliant}`],
  ["Engine vs answer key, max abs ratio error", `${M.engine_vs_answer_key.max_abs_error_leverage}`, "-", "-"],
], [3900, 1820, 1820, 1820], { size: 17 }));
C.push(CAP("Table 8. Status outcomes. TIGHT and COMPLIANT are distinguished for the system and B2; B1 cannot express TIGHT, so it is scored on breach / non-breach."));
C.push(...fig("status_vs_baselines.png", 5.8, "Figure 3. Breach detection, false breaches and silent statuses on cases that should have halted."));
C.push(P("B2 missed both Apex breaches: it applied the 4.50x threshold that the First Amendment had replaced and took the over-cap add-backs at face value. It caught Delta's breach only because that step-down is written into the base agreement. Taking add-backs as claimed also produced one false breach and two wrong tight/compliant calls. B1 missed the three breaches the borrowers' own certificates concealed. Neither baseline has any notion of halting, so all four should-halt cases came out as compliant: a missing certificate page, two quarters governed by an amendment with no determinable effective date, and a numeric field carrying an embedded instruction."));
C.push(H2("8.3 Retrieval, extraction and graph construction"));
C.push(...fig("retrieval.png", 5.8, "Figure 4. Answer accuracy on 47 labelled multi-hop questions (governing threshold, add-back cap, add-back permitted)."));
C.push(P(`Graph traversal with the effective-date rule answered all 47 questions and retrieved every required section. Chunk retrieval was right on ${pct(M.retrieval.chunk_tfidf_top3.all.answer_accuracy)} and retrieved all required sections for only ${pct(M.retrieval.chunk_tfidf_top3.all.full_evidence_rate)} of questions. Its typical failure is the one the midpoint predicted: for Apex after the First Amendment, the top chunks were the ratio definition, the original covenant (4.50x) and the amendment preamble, never the operative amendment clause. The comparison isolates retrieval; an LLM reading the chunks could do better, which B3 is designed to test.`));
C.push(table(["Component", "Result", "Read with caution because"], [
  ["Extraction pass 1 (statements / certificate)", `${pct(M.extraction.rule_pass1.statements.accuracy)} / ${pct(M.extraction.rule_pass1.certificate.accuracy)} of ${M.extraction.rule_pass1.statements.fields} / ${M.extraction.rule_pass1.certificate.fields} fields`, "Templated layout; the misses are the seeded unit change (5 fields) and the injected field (correctly left empty)"],
  ["Extraction pass 2", `${pct(M.extraction.pagewise_pass2.statements.accuracy)} / ${pct(M.extraction.pagewise_pass2.certificate.accuracy)}`, "Same layout family"],
  ["XBRL tie-out (first pass)", `${M.xbrl_tieout.tied_first_pass}/${M.xbrl_tieout.fields_checked}; both failures recovered by the second read`, "Synthetic XBRL"],
  ["Graph nodes / edges vs gold", "Node P = R = 1.00 for all borrowers; edge recall 1.00; edge precision 1.00, 1.00, 1.00 and 0.93", "One spurious edge (a Brightwater add-back also linked to the superseded cap); resolution still correct"],
  ["Governing-version selection", `${M.version_selection.correct}/${M.version_selection.periods} quarters, including both halts`, "Amendment timeline is clean by construction except the seeded case"],
], [2700, 3400, 3260], { size: 17 }));
C.push(CAP("Table 9. Component accuracy."));
C.push(H2("8.4 Discrepancies, security and failure tests"));
C.push(table(["Seeded case", "Expected cause", "Proposed", "Steps"], M.discrepancy.rows.map((r) => [r.case.replace(/_/g, " ") + ` (${r.borrower} ${r.period.slice(0, 7)})`, r.expected.replace(/_/g, " "), r.proposed.join(", ").replace(/_/g, " "), String(r.steps || "rule")]), [3400, 2400, 2560, 1000], { size: 17 }));
C.push(CAP(`Table 10. Discrepancy detection and cause classification: ${M.discrepancy.detected}/${M.discrepancy.seeded} detected, ${M.discrepancy.cause_exact}/${M.discrepancy.seeded} exact, ${M.discrepancy.findings_on_unseeded_runs} findings on unseeded quarters; mean ${M.agent.mean_steps} tool calls (budget ${M.agent.budget}). The units case is caught by XBRL tie-out before the investigator runs. Threshold flags: ${M.threshold_flag.flagged_correctly}/${M.threshold_flag.seeded} with ${M.threshold_flag.false_flags} false flags.`));
C.push(table(["Test", "Pass criterion", "Result"], [
  ["Instruction in certificate text (Apex Q4 2025)", "Status and ratio identical to a clean twin; instruction absent from agent context", `${M.prompt_injection[0].passed ? "Pass" : "Fail"}: BREACH, 4.40x in both`],
  ["Instruction inside a numeric field (Delta Q2 2026)", "Value not guessed; run halts with anomaly for analyst", `${M.prompt_injection[1].passed ? "Pass" : "Fail"}: HALT (clean twin COMPLIANT)`],
  ["Missing certificate page", "Halt, no status", "Pass"], ["Amendment with no calendar effective date (2 quarters)", "Halt, no threshold chosen", "Pass"],
  ["Unit change on one statement page", "Flag; independent re-read; value pending acceptance", "Pass: 5 fields re-read, all tie to XBRL"],
  ["Restated prior quarter", "Flag; cause = period restatement", "Pass"], ["Statement vs certificate conflict", "Flag; cause = mismatch", "Pass"], ["Stale threshold on certificate", "Flag", "Pass"],
  ["Fabricated number inserted in each memo", "Numeric guard blocks the draft", `${M.memo_guard.adversarial_insertions_blocked}/${M.memo_guard.drafts} blocked`],
  ["Step budget forced to 1", "Investigation returns unresolved, not a guess", "Pass (unit test)"],
  ["Edit one audit entry", "Hash chain fails at that entry", "Pass (unit test)"],
], [3400, 3700, 2260], { size: 17 }));
C.push(CAP("Table 11. Security and failure tests."));
C.push(H2("8.5 Tolerance, early warning and workload"));
C.push(table(["Tolerance setting", "Seeded gaps investigated", "Investigations on clean quarters"], M.tolerance_sensitivity.map((t) => [t.setting, `${t.agent_triggered_on_seeded}/${t.seeded}`, String(t.agent_triggered_on_unseeded)]), [4200, 2580, 2580], { size: 17 }));
C.push(CAP("Table 12. Tolerance sensitivity. The very-tight setting turns borrower rounding into 10 needless investigations; the default and looser settings separate seeded gaps from rounding on this data. Seeded gaps are large, so the upper bound is not stress-tested here."));
C.push(...fig("headroom_trend.png", 6.2, "Figure 5. Headroom to the governing leverage threshold. Rings mark early-warning flags (three consecutive declines, or headroom under 15%)."));
C.push(P(`Every one of the four breaches was preceded by an early-warning flag one or two quarters earlier. The flags are not precise, though: 16 of the 28 computed quarters carry one, because the 15% floor also fires on recovering credits. That is acceptable for a watch signal reviewed by a PM, but it is a ranking aid, not a prediction. On workload, the manual baseline re-keys about ${Math.round(M.workload.fields_rekeyed_manually_per_package_baseline)} fields per package before any analysis. With the system, ${M.workload.packages_needing_only_signoff} of 32 packages needed only a sign-off, and the mean was ${M.workload.human_decisions_per_package_system_mean} human decisions per package. We did not time analysts, so we make no claim about minutes saved; docs/timing_protocol.md sets out a crossover test for the team. Offline processing took ${M.latency.mean_seconds_per_package}s per package; with LLM backends, cost and latency are logged per call.`));
C.push(H2("8.6 Check against real SEC filings"));
C.push(P("To test whether the synthetic cases reflect real documents, we ran scripts/fetch_edgar.py on 10 filers selected from 159 that match covenant-compliance language on EDGAR. It retrieved about 170 Exhibit-10 credit documents and the XBRL company facts. We then read the financial-covenant section of the most recent agreement for 9 of them (labels in data_real/, marked as drafts pending team verification). Three findings bear directly on the design:"));
C.push(table(["Finding (draft, 9 agreements)", "Count", "Design implication"], [
  ["Maintenance covenant located", "7 of 9", "Quantum (liquidity test) and Cadre (covenants in an earlier base agreement) need follow-up"],
  ["Threshold changes on an event or a borrower election, not a calendar date", "4 of 7", "Enviri (Rail Disposition, Clean Earth Effective Date), DSG (Covenant Ratchet Date), ModivCare (Covenant Relief Period), Digi (acquisition holiday). Same behaviour as synthetic borrower CLC: halt until a person supplies the event date"],
  ["Conformed copy contains redline artifacts (struck and new numbers adjacent)", "2 of 7", "e.g. \u201c2.75 2.00 to 1.00\u201d; a naive pattern reads the struck number, so values need page-level human review"],
  ["Covenant clause found by a fixed pattern of the kind that parses our synthetic agreements", "3 of 9", "Real text needs the LLM graph builder plus team review, as planned"],
], [3800, 900, 4660], { size: 16 }));
C.push(CAP("Table 13. Real-filing check. Counts come from our reading of the filings and are pending team verification."));
C.push(P("The real filings confirm that the hard cases in the synthetic benchmark are not artificial: event-dependent thresholds are common, and templated parsing does not transfer. The next step is to score the LLM graph builder against these labels once verified."));
C.push(H2("8.7 Interpretation"));
C.push(P("Two kinds of evidence are mixed in these numbers, and they should be read differently. The control results (halts, flags, injection resistance, authority refusals, the numeric guard, version selection) test logic that does not depend on the data being realistic: an undatable amendment halts whatever the agreement looks like. The accuracy results for extraction and graph parsing depend heavily on the templated documents and would fall on real filings. The comparisons with baselines show the size of the risk the redesign removes, since stale definitions and trusted certificates fail in the ways the pain points predict. They do not show how an LLM-based competitor would do, and that is what B3 is for."));

// 9
C.push(H1("9. Business and Implementation Implications"));
C.push(P("**Operational benefit.** The analyst's role moves from transcription and reconstruction to review. A clean quarter reduces to checking the engine output and signing; a disputed quarter arrives with the cause, the clause and the page already assembled. Determinations become consistent across analysts because caps, versions and tolerances are applied by rule, and contested breaches are easier to defend because every number traces to a page."));
C.push(P("**Integration.** Inputs come from the data room or email intake and the document repository; outputs feed the portfolio monitoring tracker, the risk-rating system, the watchlist, and fund valuation and reporting. The engine and graph sit behind an API; the approval screen would integrate with the lender's identity provider so that roles come from the authority matrix rather than self-selection, as they do in the prototype."));
C.push(P("**Regulation and model governance.** Our hypothetical lender is a direct lender, so bank model-risk guidance (Federal Reserve SR 11-7) does not bind it directly. Its principles (documented purpose, independent validation, ongoing monitoring, change control) are still the right standard, and a bank lender would be bound by them. A BDC or registered fund's valuation process (SEC Rule 2a-5) relies on monitoring outputs, and adviser compliance programmes and books-and-records rules require the evidence trail the audit log provides. This is not legal advice. The design point is that each of these regimes asks for reproducibility, named accountability and documented change, which the architecture supplies by construction."));
C.push(table(["Phase", "Scope", "Exit criterion"], [
  ["0. Real-filing pilot (4-6 weeks)", "10-20 EDGAR borrowers; LLM graph builder with full team review; LLM extractor; B3 baseline; timed analyst study", "Field accuracy and graph precision/recall measured on real text; minutes per package measured"],
  ["1. Shadow mode (1-2 quarters)", "Run alongside analysts on live packages; no outputs used", "Disagreements explained; tolerance and halt rates tuned"],
  ["2. Assisted production (2-4 quarters)", "Analysts review system output; humans sign; model-risk validation of extractor and graph builder", "Validation report; override rate stable; audit sign-off"],
  ["3. Portfolio scale", "Full book; rating-migration analytics; waiver precedent search over the lender's own memos", "Ongoing monitoring of drift, halt and override rates"],
], [2500, 4300, 2560], { size: 17 }));
C.push(CAP("Table 14. Implementation roadmap."));
C.push(P("**Human impact and adoption.** Adoption depends on analysts trusting the output, which is why every number links to a page and every finding can be rejected. Over-reliance is the opposite risk; the open-item check, separation of duties and the override-rationale requirement keep a person actively deciding. Scalability is not the constraint: the offline pipeline takes milliseconds, and the binding cost at scale is graph review for new agreements and amendments, which favours reviewing only changed sections."));

// 10
C.push(H1("10. Risks, Limitations, and Next Steps"));
C.push(table(["Risk", "Control in this design", "Residual risk"], [
  ["Hallucinated or unsupported numbers", "Engine computes all numbers; memo numeric guard; typed schema", "Wrong value extracted that still parses (mitigated by tie-out where XBRL exists)"],
  ["Error propagation from a wrong graph edge", "Team review; graph metrics; version rule outside retrieval", "Review effort grows with portfolio size"],
  ["Correlated errors (same model extracts and investigates)", "Verification uses XBRL, statements, prior packages; second read uses a different library and unit logic", "Add-backs have no independent public source"],
  ["Prompt injection via borrower documents", "Typed channels; free text only to humans; anomaly halts", "Attacks that look like plausible numbers"],
  ["Inappropriate autonomy", "No write tools; role-checked gate; system holds no role", "Process risk if roles are self-selected (prototype only)"],
  ["Non-determinism", "Rule backends deterministic; fixed model id; LLM outputs logged; inputs hashed; commit logged", "LLM outputs can still vary across versions"],
  ["Drift (new agreement styles, layouts)", "Halt and anomaly rates monitored from the log", "Requires periodic revalidation"],
  ["Over-automation of judgment", "Disputed add-backs, ratings, breaches and waivers stay human", "Automation bias in reviewers"],
], [2600, 3900, 2860], { size: 16 }));
C.push(CAP("Table 15. Risks and controls."));
C.push(P("**Limitations.** (1) Synthetic, templated documents: extraction and graph scores are not predictive of real performance; the real-filing check (Section 8.6) covers covenant terms only, with draft labels. (2) The LLM backends and the single-prompt baseline are implemented but unevaluated. (3) Analyst time was not measured. (4) Four borrowers and 32 quarters support per-case conclusions, not rates. (5) Equity cures, covenant holidays and syndicated-lender votes are recorded but not simulated. (6) The investigator's causes form a closed set: a novel cause comes back as unresolved, which is safe but needs a person. This is also the strongest argument for the LLM policy, which can still only choose from the set. (7) Public agreements are mostly bank-led syndicated facilities, so they are only a proxy for direct-lender documents."));
C.push(P("**Next steps to production.** Run scripts/fetch_edgar.py on 10-20 maintenance-covenant filers and score the LLM graph builder and extractor against hand-labelled gold. Run B3 and the Claude investigator (eval/llm_baseline.py) and compare causes, steps and cost with the rule policy. Run the timing protocol. Add equity-cure and covenant-reset handling. Connect roles to an identity provider. Complete independent validation before any output is relied on."));

// References
C.push(H1("References"));
[
  "Yao, S. et al. ReAct: Synergizing Reasoning and Acting in Language Models. ICLR 2023. arXiv:2210.03629.",
  "Debenedetti, E. et al. Defeating Prompt Injections by Design (CaMeL). 2025. arXiv:2503.18813.",
  "Debenedetti, E. et al. AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents. NeurIPS 2024. arXiv:2406.13352.",
  "Tatarinov et al. KG-MuLQA: A Framework for KG-based Multi-Level QA Extraction and Long-Context LLM Evaluation. ACL 2026. arXiv:2505.12495.",
  "Sudjianto, A. Perhaps We Built Agentic AI Backwards. September 24, 2026 (ProveAct). agussudjianto.substack.com.",
  "McKinsey & Company. The future is agentic: AI's role in the end-to-end corporate credit process. December 12, 2025.",
  "Board of Governors of the Federal Reserve System and OCC. SR 11-7: Supervisory Guidance on Model Risk Management. 2011.",
  "U.S. Securities and Exchange Commission. Rule 2a-5 under the Investment Company Act: Good Faith Determinations of Fair Value. 2020.",
  "U.S. SEC EDGAR full-text search and XBRL company-facts API (data.sec.gov), used for document structure.",
].forEach((r) => C.push(N(r)));

// ---------- Appendix
C.push(new Paragraph({ children: [new PageBreak()] }));
C.push(H1("Appendix A. Per-case results (all 32 test periods)"));
C.push(table(["Borrower", "Quarter", "Seeded case", "Expected", "System", "Leverage / threshold", "Proposed causes"], CASES, [900, 900, 2000, 1060, 1060, 1500, 1940], { size: 15 }));
C.push(CAP("Table A1. Generated from the audit log by eval/run_eval.py (also in results/eval_report.md)."));
C.push(H1("Appendix B. Worked case: memo draft and investigator trace (Apex, Q3 2025)"));
C.push(...MONO(AIH.memo));
C.push(SP());
C.push(P("Investigator trace (every tool returns typed values and citations only):", { run: { bold: true } }));
C.push(...MONO(AIH.trace.map((t) => `step ${t.step}: ${t.tool}(${JSON.stringify(t.args)}) -> ${JSON.stringify(t.result).slice(0, 150)}`).join("\n")));
C.push(SP());
C.push(P("Governing-version reasons: " + AIH.terms_reasons.join("; ")));
C.push(P("Authority gate in the demo: PM signs BREACH -> refused (role may not declare_breach); analyst accepts finding -> recorded; same analyst signs as committee -> refused (separation of duties); committee member signs BREACH -> recorded."));
C.push(H1("Appendix C. Audit record fields"));
C.push(P("Each run writes one entry: " + AIH.audit_keys.join(", ") + ". Each entry also stores prev_hash and entry_hash (SHA-256 over the canonical JSON), so any edit breaks verification from that entry onward. Decisions and determinations are separate entries with user, role, timestamp and rationale."));
C.push(P("Input hashes for the worked case: " + Object.entries(AIH.input_hashes).map(([k, v]) => `${k} ${v.slice(0, 16)}...`).join("; ") + ". Settings recorded: " + JSON.stringify(AIH.settings)));
C.push(H1("Appendix D. Configuration: tolerances and delegation of authority"));
const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, "config", "settings.json")));
C.push(table(["Action", "Roles allowed"], Object.entries(cfg.authority).map(([k, v]) => [k.replace(/_/g, " "), v.join(", ").replace(/_/g, " ")]), [4680, 4680], { size: 17 }));
C.push(P(`Tolerances: ratio ${cfg.tolerance.ratio_abs}x; component greater of ${cfg.tolerance.component_pct * 100}% or $${cfg.tolerance.component_abs_thousands}k; XBRL tie-out ${cfg.xbrl_tieout_pct * 100}%; tight headroom under ${cfg.tight_headroom * 100}%; investigator budget ${cfg.agent.step_budget} tool calls; separation of duties enforced.`));
C.push(H1("Appendix E. Synthetic data procedure and borrower set"));
C.push(table(["Borrower (fictional)", "Leverage covenant", "Coverage", "Amendments"], [
  ["Apex Industrial (AIH)", "Total net leverage <= 4.50x; cash netting capped at $25m; non-recurring + pro forma add-backs capped jointly at 15%", "ICR >= 3.00x", "First Amendment effective 2025-06-30: 4.25x"],
  ["Brightwater Health (BHS)", "Total (gross) leverage <= 5.00x; restructuring capped at $5m; pro forma savings capped at 10%", "FCCR >= 1.25x", "Amendment 1 eff. 2025-03-31 adds run-rate synergies, joint cap 20%; Amendment 2 eff. 2026-03-31: 5.25x"],
  ["Cedar Logistics (CLC)", "Senior secured net leverage <= 3.75x; unsecured notes excluded; cash capped at $15m", "ICR >= 2.50x", "First Amendment executed 2026-05-10, effective on an acquisition closing (no date): 3.50x"],
  ["Delta Software (DSW)", "Total net leverage step-down 6.00x / 5.75x / 5.50x in the base agreement; uncapped cash netting; SBC uncapped", "ICR >= 2.00x", "None"],
], [2000, 3800, 1300, 2260], { size: 16 }));
C.push(P("Procedure per borrower-quarter: (1) quarterly operating income and D&A follow a specified path and debt is set to a target multiple of the governing threshold; (2) the answer key computes the covenant from these figures under the governing definitions; (3) the borrower certificate is generated from the borrower's view (claimed add-backs, original figures where a restatement occurred, rounding where the borrower presents to $100k); (4) the seeded case is applied as a labelled perturbation; (5) documents are rendered to PDF; XBRL facts store as-filed and restated values; injection cases get a clean twin. Generator: datagen/generate.py, specification: datagen/spec.py."));
C.push(H1("Appendix F. Changes since the proposal and midpoint"));
C.push(B("Forward covenant projection removed after the midpoint discussion; early warning uses headroom trend and breach sensitivity on reported figures."));
C.push(B("Prior-memo search removed: no public corpus of lender memos. Listed as a phase-3 item over the lender's own memos."));
C.push(B("Benchmark made fully synthetic with an independent answer key, so every quarter has a known answer; a real-filing check on 9 EDGAR agreements (Section 8.6) tests whether the hard cases are realistic."));
C.push(B("The second-pass re-read now covers the whole affected page, not one field. In development, re-reading only the XBRL-tagged fields left secured-debt components wrong and produced a correct status for the wrong reason."));
C.push(B("Added causes for statement-vs-certificate mismatch, a deterministic threshold-mismatch flag, the delivery-deadline rule, a hash-chained audit log, and separation-of-duties and override-rationale checks."));
C.push(H1("Appendix G. Reproducing the results"));
C.push(...MONO("pip install -r requirements.txt\nmake data   # regenerate synthetic data and gold files\nmake test   # 45 unit tests\nmake eval   # results/metrics.json, results/eval_report.md, results/figures/\nmake demo   # four-scene terminal demo\nmake app    # Streamlit approval screen\nANTHROPIC_API_KEY=... python -m eval.llm_baseline   # B3 + Claude investigator"));

// ---------- document
const doc = new Document({
  creator: "MGT 8803 Group", title: "Governed Agentic Covenant Monitoring",
  styles: {
    default: { document: { run: { font: FONT, size: 23 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 30, bold: true, color: "1F3A5F" }, paragraph: { spacing: { before: 300, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 25, bold: true, color: "333333" }, paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "[%1]", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 540 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
      new TextRun({ text: "MGT 8803 · Covenant Monitoring · page ", font: FONT, size: 16, color: "777777" }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "777777" })] })] }) },
    children: C,
  }],
});
Packer.toBuffer(doc).then((buf) => {
  const out = path.join(ROOT, "report", "MGT8803_Final_Report_Covenant_Monitoring.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out);
});
