# Covenant Monitoring — Governed Agentic Workflow Prototype

MGT 8803 AI in Finance · Final Project · Track 1: Lending and Private Credit  
Vivan Jain · Srivant Vishnuvajjala · Vidhi Chaturvedi · Manasi Prasad

Quarterly covenant compliance and early-warning monitoring at a middle-market direct lender, redesigned so that
**models propose, deterministic code computes and verifies, and named people decide.**

```
borrower package ──► extraction (typed, page-cited) ──► verification (XBRL, prior packages, statements, arithmetic)
credit agreement ──► knowledge graph ──► governing version by effective date (halt if undeterminable)
                                   └──► deterministic covenant engine ──► provisional status + sensitivity + trend
                         gap > tolerance ──► bounded investigator (read-only tools, closed-set causes, 12-step budget)
                                              ──► draft memo (numeric guard) ──► approval gate (role matrix) ──► audit log
```

## Results on the 32-period synthetic benchmark (`results/metrics.json`)

| | This system | Stale-definitions spreadsheet | Trust borrower certificate |
|---|---|---|---|
| Exact status match (of 32) | **32** | 23 | 21 |
| Breaches detected (of 4) | **4** | 2 | 1 |
| False breaches | **0** | 1 | 0 |
| Should-halt cases reported compliant (of 4) | **0** | 4 | 4 |

Definition retrieval, 47 labelled multi-hop questions: knowledge graph + effective-date rule 100% vs chunk retrieval (TF-IDF top-3) 53%.
Seeded discrepancy causes identified 8/8; prompt-injection tests 2/2; failure tests 8/8; adversarial memo insertions blocked 32/32.
All 4 breaches were preceded by an early-warning flag 1-2 quarters earlier (16 of 28 quarters flagged, so treat it as a watch signal).
Full per-case table: `results/eval_report.md`.

**Read the limitations before quoting these numbers.** The benchmark is synthetic and the agreement language is templated,
so extraction and graph parsing are near-perfect by construction. What the numbers do show is that the controls behave
as designed on every seeded failure type. See report Section 10.

## Quick start

```bash
pip install -r requirements.txt
make data      # regenerate synthetic borrowers, PDFs, XBRL facts, answer key  (python -m datagen.generate)
make test      # 45 unit tests: engine vs answer key, version resolution, injection, authority gate, audit chain
make eval      # full evaluation -> results/metrics.json, results/eval_report.md, results/figures/*.png
make demo      # scripted terminal demo (4 scenes)
make app       # Streamlit approval screen  (streamlit run app/approval_app.py)
```

Optional LLM backends (set `ANTHROPIC_API_KEY`):

```bash
python -m eval.llm_baseline     # single-prompt LLM baseline + Claude ReAct investigator on the same tools
# config/settings.json: "agent.backend": "claude", "extraction.backend": "claude"
```

## Repository map

| Path | What it is |
|---|---|
| `cov/extract.py` | Two independent PDF extractors (pdfplumber / PyMuPDF, doc-level vs page-level units); strict numeric validator |
| `cov/extract_llm.py` | Claude extractor (same schema + validator) for real, variable layouts |
| `cov/kg.py` | Agreement knowledge graph (NetworkX), rule builder, `resolve_terms()` governing-version rule |
| `cov/kg_llm.py` | Claude graph builder for real EDGAR agreements |
| `cov/engine.py` | Deterministic covenant math: add-back caps, leverage / ICR / FCCR, headroom, sensitivity, early warning |
| `cov/verify.py` | XBRL tie-out, period consistency, statement vs certificate, arithmetic, threshold check, delivery deadline |
| `cov/agent.py` | Read-only toolbox, closed-set causes, step budget, rule investigator |
| `cov/agent_llm.py` | Claude ReAct investigator over the same toolbox |
| `cov/memo.py` | Draft memo with numeric guard |
| `cov/approval.py` | Delegation-of-authority gate, separation of duties, override rationale |
| `cov/audit.py` | Append-only JSONL audit log with SHA-256 hash chain |
| `cov/pipeline.py` | Orchestration (Generate → Verify → Constrain → Decide → Gate → Record) |
| `cov/retrieval.py` | KG retrieval vs chunk-retrieval baseline |
| `app/approval_app.py` | Streamlit analyst / approver screen |
| `datagen/` | Synthetic data specification and generator (answer key computed independently of the engine) |
| `eval/` | Evaluation harness and LLM baselines |
| `scripts/fetch_edgar.py` | EDGAR / XBRL fetcher for the real-filing borrower screen |
| `config/settings.json` | Tolerances, step budget, authority matrix (never in prompts) |
| `docs/` | Data notes, demo script, timing protocol |
| `report/` | Final report (.docx/.pdf), presentation (.pptx/.pdf) and the scripts that build them from `results/` |

## Data

All data in `data/` is **synthetic** and labelled as such inside every document. Borrower names are invented.
Agreement structure (definitions, financial covenants, add-back caps, step-downs, amendments, Exhibit D certificate)
follows credit agreements filed as Exhibit 10 on SEC EDGAR. No confidential, employer, or personal data. See `docs/data.md`.
