"""Agreement knowledge graph and deterministic governing-version resolution.

Nodes: covenant, threshold, defined_term, addback, cap, netting, amendment.
Edges: has_threshold, uses, permits, capped_by, sets, adds.
Every node carries doc, section and page so any answer can be cited back to the agreement.

Two builders share one schema:
  * RuleKGBuilder  - pattern parser for EDGAR-style covenant language (offline, deterministic)
  * LLMKGBuilder   - in kg_llm.py; Claude extracts the same typed nodes/edges (for real agreements)

Which version of a term governs a test period is NOT a retrieval or model question: resolve_terms()
picks it by effective date and halts when an amendment's effective date cannot be determined.
"""
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import networkx as nx

from cov.common import DATA

SEC_RE = re.compile(r"^Section (\S+)\. (.+)\.$")
DATE_TXT = r"(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}"
RATIO_RE = re.compile(r"(\d+\.\d{2}) to 1\.00")


def _iso(txt):
    return datetime.strptime(txt, "%B %d, %Y").strftime("%Y-%m-%d")


def cov_key(label):
    return label.lower().replace(" ratio", "").replace(" ", "_")


def load_documents(borrower, root: Path = None):
    root = root or DATA / "borrowers" / borrower / "agreement"
    docs = {}
    for f in sorted(root.glob("*.txt")):
        page, secs, cur = 1, [], None
        for ln in f.read_text().splitlines():
            m = re.match(r"\[\[PAGE (\d+)\]\]", ln)
            if m:
                page = int(m.group(1))
                continue
            m = SEC_RE.match(ln)
            if m:
                cur = {"section": m.group(1), "heading": m.group(2), "body": "", "page": page}
                secs.append(cur)
            elif cur is not None and ln.strip():
                cur["body"] += ln.strip() + " "
        for s in secs:
            s["body"] = re.sub(r"(\w)- (\w)", r"\1-\2", s["body"]).strip()
        docs[f.stem] = {"id": f.stem, "sections": secs, "text": f.read_text()}
    return docs


class RuleKGBuilder:
    name = "rule"

    def build(self, borrower, docs) -> nx.DiGraph:
        G = nx.DiGraph(borrower=borrower, builder=self.name)
        base = docs["BASE"]
        self._base(G, base)
        for did in sorted(d for d in docs if d != "BASE"):
            self._amendment(G, docs[did])
        return G

    # ------------------------------------------------------------------ base agreement
    def _base(self, G, doc):
        letters = {}
        cap_sections = []
        for s in doc["sections"]:
            sid, head, body, pg = s["section"], s["heading"], s["body"], s["page"]
            cite = {"doc": "BASE", "section": sid, "page": pg}
            if sid == "0":
                m = re.search(r"among (.+?), as the Borrower", body)
                if m:
                    G.graph["borrower_name"] = m.group(1)
            if head == "Defined Term: Consolidated EBITDA":
                G.add_node("term:Consolidated EBITDA", type="defined_term", **cite)
                for letter, name in re.findall(r"\(([a-h])\) ([A-Z][A-Za-z\- ]+?)(?=;|\.)", body):
                    letters[letter] = name.strip()
                    G.add_node(f"addback:{name.strip()}", type="addback", **cite)
                    G.add_edge("term:Consolidated EBITDA", f"addback:{name.strip()}", rel="permits")
            elif head.startswith("Defined Term: Consolidated EBITDA (limitation)"):
                cap_sections.append((s, cite))
            elif head == "Defined Term: Net Debt":
                if "No cash shall be netted" in body:
                    cap = 0.0
                elif "shall not exceed" in body:
                    cap = float(re.search(r"\$([\d,]+)", body).group(1).replace(",", "")) / 1000
                else:
                    cap = None
                G.add_node("netting:cash", type="netting", cash_cap=cap, **cite)
            elif head == "Defined Term: Senior Secured Debt":
                G.add_node("term:Senior Secured Debt", type="defined_term", **cite)
            elif head == "Defined Term: Total Debt":
                G.add_node("term:Total Debt", type="defined_term", **cite)
            elif head.startswith("Financial Covenant: "):
                label = head.split(": ", 1)[1]
                key = cov_key(label)
                op = "max" if "to exceed" in body else "min"
                kind = "leverage" if "Leverage" in label else ("fcc" if "Fixed Charge" in label else "icr")
                G.add_node(f"cov:{key}", type="covenant", label=label, op=op, kind=kind, **cite)
                G.add_edge(f"cov:{key}", "term:Consolidated EBITDA", rel="uses")
                if op == "min":
                    G.nodes[f"cov:{key}"]["threshold"] = float(RATIO_RE.search(body).group(1))
                    continue
                if "opposite such Test Period:" in body:
                    parts = body.split("opposite such Test Period:", 1)[1].rstrip(". ").split(";")
                    for clause in parts:
                        val = RATIO_RE.search(clause).group(1)
                        m2 = re.search(r"on or before (" + DATE_TXT.replace("(January", "(?:January") + ")", clause)
                        through = _iso(m2.group(1)) if m2 else None
                        nid = f"thr:{key}:BASE:{through or 'thereafter'}"
                        G.add_node(nid, type="threshold", value=float(val), through=through, **cite)
                        G.add_edge(f"cov:{key}", nid, rel="has_threshold")
                else:
                    val = float(RATIO_RE.search(body).group(1))
                    nid = f"thr:{key}:BASE:thereafter"
                    G.add_node(nid, type="threshold", value=val, through=None, **cite)
                    G.add_edge(f"cov:{key}", nid, rel="has_threshold")
        for s, cite in cap_sections:
            body = s["body"]
            members = re.findall(r"clause \(([a-h])\)", body)
            if "%" in body.split("shall not exceed")[1][:20]:
                ctype, val = "pct", float(re.search(r"exceed ([\d.]+)%", body).group(1)) / 100
            else:
                ctype, val = "abs", float(re.search(r"exceed \$([\d,]+)", body).group(1).replace(",", "")) / 1000
            cid = f"cap:{s['section']}:BASE"
            G.add_node(cid, type="cap", cap_type=ctype, value=val, **cite)
            for m in members:
                G.add_edge(f"addback:{letters[m]}", cid, rel="capped_by")
        basis = "secured" if "term:Senior Secured Debt" in G else "total"
        for n, d in G.nodes(data=True):
            if d["type"] == "covenant" and d["kind"] == "leverage":
                d["debt_basis"] = basis

    # ------------------------------------------------------------------ amendments
    def _amendment(self, G, doc):
        did = doc["id"]
        secs = {s["section"]: s for s in doc["sections"]}
        pre = secs["A0"]["body"]
        execution = _iso(re.search(r"dated as of (" + DATE_TXT.replace("(January", "(?:January") + ")", pre).group(1))
        eff_body = secs["A3"]["body"]
        m = re.search(r"effective as of (" + DATE_TXT.replace("(January", "(?:January") + ")", eff_body)
        effective = _iso(m.group(1)) if m else None
        G.add_node(f"amd:{did}", type="amendment", execution=execution, effective=effective,
                   effective_text=None if m else eff_body, doc=did, section="A3", page=secs["A3"]["page"])
        for sid, s in secs.items():
            body, cite = s["body"], {"doc": did, "section": sid, "page": s["page"]}
            m = re.search(r"^Section (\S+) of the Credit Agreement is hereby amended by replacing the reference to "
                          r"\"[\d.]+ to 1\.00\" with \"([\d.]+) to 1\.00\"", body)
            if m:
                target = next(n for n, d in G.nodes(data=True) if d["type"] == "covenant" and d["section"] == m.group(1))
                key = target.split(":", 1)[1]
                nid = f"thr:{key}:{did}"
                G.add_node(nid, type="threshold", value=float(m.group(2)), through=None, **cite)
                G.add_edge(f"amd:{did}", nid, rel="sets")
                G.add_edge(target, nid, rel="has_threshold")
                continue
            m = re.search(r"amended and restated so that .*? shall not exceed ([\d.]+)% of", body)
            if m and sid.startswith("A2"):
                target_sec = re.search(r"^Section (\S+) of the Credit Agreement", body).group(1)
                cid = f"cap:{target_sec}:{did}"
                G.add_node(cid, type="cap", cap_type="pct", value=float(m.group(1)) / 100, restates=target_sec, **cite)
                G.add_edge(f"amd:{did}", cid, rel="sets")
                for a, b, d in list(G.edges(data=True)):
                    if d["rel"] == "capped_by" and G.nodes[b].get("section") == target_sec and G.nodes[b]["doc"] == "BASE":
                        G.add_edge(a, cid, rel="capped_by")
                continue
        for sid, s in secs.items():  # second pass: add-backs (may refer to caps restated above)
            m = re.search(r"permitting the add-back of ([A-Z][A-Za-z\- ]+?), which shall be subject to the same "
                          r"limitation as ([A-Z][A-Za-z\- ]+?)\.", s["body"])
            if m:
                name, like = m.group(1), m.group(2)
                cite = {"doc": did, "section": sid, "page": s["page"]}
                G.add_node(f"addback:{name}", type="addback", **cite)
                G.add_edge(f"amd:{did}", f"addback:{name}", rel="adds")
                G.add_edge("term:Consolidated EBITDA", f"addback:{name}", rel="permits")
                for _, cid, d in G.out_edges(f"addback:{like}", data=True):
                    if d["rel"] == "capped_by":
                        G.add_edge(f"addback:{name}", cid, rel="capped_by")


@dataclass
class Terms:
    period: str
    lev_key: str = ""
    lev_label: str = ""
    lev_section: str = ""
    lev_threshold: Optional[float] = None
    debt_basis: str = "total"
    cash_cap: Optional[float] = None
    cov_key: str = ""
    cov_label: str = ""
    cov_kind: str = ""
    cov_min: Optional[float] = None
    addbacks: dict = field(default_factory=dict)      # name -> cap_id | None
    caps: dict = field(default_factory=dict)          # cap_id -> {cap_type, value, section, doc}
    versions: list = field(default_factory=lambda: ["BASE"])
    halt: Optional[str] = None
    evidence: dict = field(default_factory=dict)      # topic -> [(doc, section, page)]
    reasons: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def _cite(G, n):
    d = G.nodes[n]
    return (d["doc"], d["section"], d["page"])


def resolve_terms(G: nx.DiGraph, period: str) -> Terms:
    t = Terms(period=period)
    covs = [n for n, d in G.nodes(data=True) if d["type"] == "covenant"]
    lev = next(n for n in covs if G.nodes[n]["kind"] == "leverage")
    cov = next(n for n in covs if G.nodes[n]["kind"] != "leverage")
    ld, cd = G.nodes[lev], G.nodes[cov]
    t.lev_key, t.lev_label, t.lev_section, t.debt_basis = lev[4:], ld["label"], ld["section"], ld["debt_basis"]
    t.cov_key, t.cov_label, t.cov_kind, t.cov_min = cov[4:], cd["label"], cd["kind"], cd["threshold"]
    t.cash_cap = G.nodes["netting:cash"]["cash_cap"] if "netting:cash" in G else None
    t.evidence["cash_netting"] = [_cite(G, "netting:cash")] if "netting:cash" in G else []
    # base threshold schedule
    base_thr = sorted([n for n in G.successors(lev) if G.nodes[n]["doc"] == "BASE" and G.nodes[n]["type"] == "threshold"],
                      key=lambda n: G.nodes[n]["through"] or "9999")
    for n in base_thr:
        if G.nodes[n]["through"] is None or period <= G.nodes[n]["through"]:
            t.lev_threshold = G.nodes[n]["value"]
            t.evidence["lev_threshold"] = [_cite(G, lev)]
            t.reasons.append(f"base schedule: {t.lev_threshold:.2f}x applies to test periods "
                             f"{'through ' + G.nodes[n]['through'] if G.nodes[n]['through'] else 'thereafter'}")
            break
    t.evidence["cov_threshold"] = [_cite(G, cov)]
    # base add-backs and caps
    term = "term:Consolidated EBITDA"
    for ab in G.successors(term):
        if G.nodes[ab]["doc"] == "BASE" and G.nodes[ab]["type"] == "addback":
            caps = [c for c in G.successors(ab) if G.nodes[c]["doc"] == "BASE"]
            t.addbacks[ab[8:]] = caps[0] if caps else None
    for n, d in G.nodes(data=True):
        if d["type"] == "cap" and d["doc"] == "BASE":
            t.caps[n] = {"cap_type": d["cap_type"], "value": d["value"], "section": d["section"], "doc": "BASE"}
    t.evidence["addbacks"] = [_cite(G, term)] + [_cite(G, c) for c in t.caps]
    # amendments in effective-date order; the rule is a date comparison, never a model judgment
    amds = sorted([n for n, d in G.nodes(data=True) if d["type"] == "amendment"],
                  key=lambda n: (G.nodes[n]["effective"] or "9999", G.nodes[n]["execution"]))
    for a in amds:
        ad = G.nodes[a]
        if ad["effective"] is None:
            if ad["execution"] <= period:
                t.halt = (f"{ad['doc']} executed {ad['execution']} has no determinable effective date "
                          f"(\"{(ad['effective_text'] or '')[:90]}...\"); governing version cannot be resolved by rule")
                t.evidence.setdefault("halt", []).append(_cite(G, a))
            continue
        if ad["effective"] > period:
            t.reasons.append(f"{ad['doc']} effective {ad['effective']} is after {period}; not applied")
            continue
        t.versions.append(ad["doc"])
        t.reasons.append(f"{ad['doc']} effective {ad['effective']} <= {period}; applied")
        for _, x, d in G.out_edges(a, data=True):
            xd = G.nodes[x]
            if xd["type"] == "threshold":
                t.lev_threshold = xd["value"]
                t.evidence["lev_threshold"] = [_cite(G, lev), _cite(G, x), _cite(G, a)]
            elif xd["type"] == "cap":
                old = f"cap:{xd['restates']}:BASE"
                t.caps.pop(old, None)
                t.caps[x] = {"cap_type": xd["cap_type"], "value": xd["value"], "section": xd["section"], "doc": xd["doc"]}
                for ab, cid in list(t.addbacks.items()):
                    if cid == old:
                        t.addbacks[ab] = x
                t.evidence["addbacks"] += [_cite(G, x), _cite(G, a)]
            elif xd["type"] == "addback":
                caps = [c for c in G.successors(x) if G.nodes[c]["type"] == "cap"]
                live = [c for c in caps if c in t.caps] or caps
                t.addbacks[x[8:]] = live[0] if live else None
                t.evidence["addbacks"] += [_cite(G, x), _cite(G, a)]
    return t


def build_all(builder=None):
    builder = builder or RuleKGBuilder()
    out = {}
    for bdir in sorted((DATA / "borrowers").iterdir()):
        docs = load_documents(bdir.name)
        out[bdir.name] = builder.build(bdir.name, docs)
    return out


def graph_to_json(G):
    return json.loads(json.dumps(nx.node_link_data(G, edges="links"), default=str))
