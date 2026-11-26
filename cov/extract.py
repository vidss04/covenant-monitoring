"""Extraction of statement line items and certificate figures into a fixed, typed schema.

Two independent deterministic extractors are provided, plus an LLM extractor (extract_llm.py):

* RuleExtractor  (pass 1): pdfplumber text layer; unit scale read once from page 1 of each document.
* PageUnitExtractor (pass 2): PyMuPDF text layer; unit scale read per page. Used only for the
  second, independent read of a field the first pass may have got wrong.

Every value carries doc + page + the source string. Anything that is not a clean number in a
numeric slot is recorded as an anomaly and the value is left empty - never guessed.
"""
import re
from pathlib import Path

import pdfplumber

from cov.common import Extraction, Field, parse_number

FIN_IS = {"Revenue": "revenue", "Operating income": "operating_income",
          "Depreciation and amortization": "da", "Interest expense": "interest_expense"}
FIN_BS = {"Cash and cash equivalents": "cash", "Revolving loans": "revolver", "Term loans": "term_loan",
          "Senior unsecured notes": "unsecured_notes", "Total debt": "total_debt",
          "Unfinanced capital expenditures": "capex", "Cash taxes paid": "cash_taxes",
          "Scheduled principal payments": "principal"}
CERT = {"EBITDA before Adjustments": "cert.ebitda_pre", "Consolidated EBITDA": "cert.cons_ebitda",
        "Total Debt": "cert.debt", "Senior Secured Debt": "cert.debt",
        "Unrestricted Cash netted": "cert.cash_netted", "Net Debt": "cert.net_debt",
        "Maximum permitted": "cert.lev_required", "Consolidated Interest Expense": "cert.interest",
        "Minimum required": "cert.cov_required", "Unfinanced Capital Expenditures": "cert.capex",
        "Cash taxes paid": "cert.taxes", "Scheduled principal payments": "cert.principal",
        "In compliance with all financial covenants": "cert.complies"}
LEV_LABELS = ("Total Net Leverage Ratio", "Total Leverage Ratio", "Senior Secured Net Leverage Ratio")
COV_LABELS = ("Interest Coverage Ratio", "Fixed Charge Coverage Ratio")
RATIO_FIELDS = {"cert.lev_ratio", "cert.cov_ratio", "cert.lev_required", "cert.cov_required"}
# Phrases typical of instructions aimed at an automated reader. Advisory flag for the analyst only;
# the control that actually matters is that free text never reaches the engine or the agent.
INSTRUCTION_RE = re.compile(r"(automated|AI\b|ignore|classify|do not escalate|reviewer|system)", re.I)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _unit_scale(text):
    if "in millions" in text:
        return 1000.0
    return 1.0  # thousands is the schema unit


def pdf_pages_plumber(path):
    with pdfplumber.open(path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def pdf_pages_mupdf(path):
    import pymupdf as fitz
    out = []
    with fitz.open(path) as doc:
        for p in doc:
            rows = {}
            for x0, y0, x1, y1, w, *_ in p.get_text("words"):
                rows.setdefault(round(y1), []).append((x0, w))
            out.append("\n".join(" ".join(w for _, w in sorted(ws)) for _, ws in sorted(rows.items())))
    return out


def _split(line, labels):
    for lab in sorted(labels, key=len, reverse=True):
        if line.startswith(lab + " "):
            return lab, line[len(lab) + 1:].strip()
    return None, None


class RuleExtractor:
    name = "rule_pass1"

    def pages(self, path):
        return pdf_pages_plumber(path)

    def scale_for(self, pages, i):
        return _unit_scale(pages[0])  # pass-1 simplification: one unit declaration per document

    def extract(self, borrower, period, pkg_dir: Path) -> Extraction:
        ex = Extraction(borrower, period)
        self._financials(ex, Path(pkg_dir) / "financials.pdf")
        self._certificate(ex, Path(pkg_dir) / "certificate.pdf")
        return ex

    # ------------------------------------------------------------------ financial statements
    def _financials(self, ex, path):
        pages = self.pages(path)
        ex.pages["financials"] = len(pages)
        for i, text in enumerate(pages):
            scale = self.scale_for(pages, i)
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            dates = []
            for ln in lines:
                found = DATE_RE.findall(ln)
                if len(found) >= 4 and ln.endswith("LTM"):
                    dates = found[:4]
                lab, rest = _split(ln, FIN_IS)
                if lab and dates:
                    toks = rest.split()
                    for q, tok in zip(dates, toks[:4]):
                        self._put(ex, f"{FIN_IS[lab]}_{q}", tok, scale, "financials", i + 1, ln)
                    continue
                lab, rest = _split(ln, FIN_BS)
                if lab:
                    self._put(ex, FIN_BS[lab], rest, scale, "financials", i + 1, ln)

    # ------------------------------------------------------------------ compliance certificate
    def _certificate(self, ex, path):
        pages = self.pages(path)
        ex.pages["certificate"] = len(pages)
        for i, text in enumerate(pages):
            scale = self.scale_for(pages, i)
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if "COMPLIANCE CERTIFICATE" in text:
                body = " ".join(l for l in lines[3:] if not l.startswith("Page "))
                for para in re.split(r"(?<=\.)\s+(?=[A-Z])", body):
                    if INSTRUCTION_RE.search(para) and "Financial Officer" not in para:
                        ex.free_text.append({"doc": "certificate", "page": i + 1, "text": para,
                                             "flag": "instruction_like_text"})
                continue
            for ln in lines:
                if ln.startswith("Add-back: "):
                    m = re.match(r"Add-back: (.+?) (\S.*)$", ln)
                    # name ends where the first numeric token starts
                    m = re.match(r"Add-back: ([A-Za-z][A-Za-z \-]+?) ([\d(].*)$", ln)
                    if m:
                        self._put(ex, f"cert.addback::{m.group(1)}", m.group(2), scale, "certificate", i + 1, ln)
                    continue
                lab, rest = _split(ln, LEV_LABELS)
                if lab:
                    self._put(ex, "cert.lev_ratio", rest, 1.0, "certificate", i + 1, ln, ratio=True)
                    continue
                lab, rest = _split(ln, COV_LABELS)
                if lab:
                    self._put(ex, "cert.cov_ratio", rest, 1.0, "certificate", i + 1, ln, ratio=True)
                    continue
                lab, rest = _split(ln, CERT)
                if lab:
                    key = CERT[lab]
                    if key == "cert.complies":
                        v = {"Yes": 1.0, "No": 0.0}.get(rest)
                        ex.fields[key] = Field(key, v, "certificate", i + 1, ln,
                                               "ok" if v is not None else "anomaly", extractor=self.name)
                    else:
                        self._put(ex, key, rest, scale, "certificate", i + 1, ln, ratio=key in RATIO_FIELDS)

    def _put(self, ex, key, tok, scale, doc, page, src, ratio=False):
        v = parse_number(tok)
        if v is None:
            ex.fields[key] = Field(key, None, doc, page, src, "anomaly",
                                   anomaly=f"non-numeric content in numeric slot: {tok!r}", extractor=self.name)
            ex.free_text.append({"doc": doc, "page": page, "text": src, "flag": "non_numeric_in_numeric_field"})
            return
        if not ratio:
            v = v * scale
        ex.fields[key] = Field(key, v, doc, page, src, "ok", extractor=self.name)


class PageUnitExtractor(RuleExtractor):
    """Second, independent read: different PDF library, unit scale detected on every page."""
    name = "pagewise_pass2"

    def pages(self, path):
        return pdf_pages_mupdf(path)

    def scale_for(self, pages, i):
        return _unit_scale(pages[i])

    def reextract_field(self, borrower, period, pkg_dir, key) -> Field:
        ex = self.extract(borrower, period, pkg_dir)
        return ex.fields.get(key) or Field(key, None, "?", None, "", "missing", extractor=self.name)


REQUIRED_FIN = ["cash", "revolver", "term_loan", "total_debt"]
REQUIRED_CERT = ["cert.ebitda_pre", "cert.cons_ebitda", "cert.debt", "cert.lev_ratio", "cert.lev_required",
                 "cert.interest", "cert.cov_ratio"]


def completeness(ex: Extraction, quarters):
    missing = [k for k in REQUIRED_FIN + REQUIRED_CERT if k not in ex.fields]
    for q in quarters:
        for k in ("operating_income", "da", "interest_expense"):
            if f"{k}_{q}" not in ex.fields:
                missing.append(f"{k}_{q}")
    anomalies = [k for k, f in ex.fields.items() if f.status == "anomaly"]
    return missing, anomalies
