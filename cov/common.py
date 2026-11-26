"""Shared types and helpers."""
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"


def load_settings():
    return json.loads((ROOT / "config" / "settings.json").read_text())


NUM_RE = re.compile(r"^\(?-?\$?\d[\d,]*(\.\d+)?\)?x?$")


def parse_number(tok: str) -> Optional[float]:
    """Strict numeric parse. Returns None if the cell is not purely numeric."""
    tok = tok.strip()
    if not NUM_RE.match(tok):
        return None
    neg = tok.startswith("(") and tok.endswith(")")
    v = float(tok.strip("()$x").replace(",", ""))
    return -v if neg else v


@dataclass
class Field:
    """One extracted value. Values are numbers or None; free text never enters `value`."""
    name: str
    value: Optional[float]
    doc: str
    page: Optional[int]
    source_text: str = ""
    status: str = "ok"            # ok | anomaly | missing
    anomaly: str = ""
    verification: str = "page_tied_only"   # xbrl_tied | xbrl_failed | page_tied_only | n/a
    extractor: str = "rule_pass1"

    def to_dict(self):
        return asdict(self)


@dataclass
class Extraction:
    borrower: str
    period: str
    fields: dict = field(default_factory=dict)       # name -> Field
    free_text: list = field(default_factory=list)    # [{doc,page,text,flag}] shown to analyst only
    pages: dict = field(default_factory=dict)        # doc -> page count

    def get(self, name) -> Optional[float]:
        f = self.fields.get(name)
        return None if f is None or f.status != "ok" else f.value

    def numeric_view(self):
        """The only form of borrower data an agent may see: typed values + citations."""
        return {k: {"value": f.value, "status": f.status, "doc": f.doc, "page": f.page,
                    "verification": f.verification} for k, f in self.fields.items()}


def fmt_k(v):
    return f"${v:,.0f}k"


def to_jsonable(o: Any):
    if hasattr(o, "to_dict"):
        return o.to_dict()
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    return o
