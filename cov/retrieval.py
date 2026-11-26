"""Definition retrieval: knowledge-graph traversal vs a chunk-retrieval baseline.

Both receive the same structured query (borrower, question type, period, item). The KG answers by
resolve_terms() and returns the cited sections it relied on. The baseline ranks agreement sections
(chunks) by TF-IDF similarity to the question text and reads the answer from the top chunk - the
behaviour of plain chunk RAG without an LLM reader.
"""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from cov.kg import resolve_terms

RATIO = re.compile(r"(\d+\.\d{2}) to 1\.00")
PCT = re.compile(r"(\d+(?:\.\d+)?)% of EBITDA")
USD = re.compile(r"\$([\d,]{6,})")


def kg_answer(G, q):
    t = resolve_terms(G, q["period"])
    if q["type"] == "governing_threshold":
        return t.lev_threshold, t.evidence.get("lev_threshold", [])
    name = q["question"].split("add-back of ")[-1].split(" in Consolidated")[0] if q["type"] == "addback_cap" else \
        q["question"].split("Is ")[1].split(" a permitted")[0]
    if q["type"] == "addback_permitted":
        ev = [e for e in t.evidence.get("addbacks", []) if e[1] in ("1.01",) or e[0] != "BASE"]
        return name in t.addbacks, ev
    cid = t.addbacks.get(name)
    cap = t.caps.get(cid) if cid else None
    ev = [("BASE", "1.01", None)] + [e for e in t.evidence.get("addbacks", []) if cap and (
        (e[0] == cap["doc"] and e[1] == cap["section"]) or (e[0] == cap["doc"] and e[1] == "A3") or
        (e[0] == "BASE" and cap["doc"] == "BASE" and e[1] == cap["section"]))]
    if cap and cap["doc"] != "BASE":
        ev += [e for e in t.evidence.get("addbacks", []) if e[0] == cap["doc"]]
    return (cap["value"] if cap else None), ev


class ChunkRetriever:
    def __init__(self, docs, k=3):
        self.chunks = [(d, s["section"], s["heading"] + ". " + s["body"]) for d, doc in docs.items() for s in doc["sections"]]
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.M = self.vec.fit_transform([c[2] for c in self.chunks])
        self.k = k

    def top(self, text):
        sims = cosine_similarity(self.vec.transform([text]), self.M)[0]
        idx = sims.argsort()[::-1][: self.k]
        return [self.chunks[i] for i in idx]

    def answer(self, q):
        hits = self.top(q["question"])
        ans = None
        for _, _, txt in hits:  # first chunk with a parsable value
            if q["type"] == "governing_threshold":
                m = RATIO.search(txt)
                if m:
                    ans = float(m.group(1))
                    break
            elif q["type"] == "addback_cap":
                m = PCT.search(txt)
                if m:
                    ans = float(m.group(1)) / 100
                    break
                m = USD.search(txt)
                if m and q.get("answer_type") == "abs":
                    ans = float(m.group(1).replace(",", "")) / 1000
                    break
            else:
                name = q["question"].split("Is ")[1].split(" a permitted")[0]
                ans = any(name in txt for _, _, txt in hits)
                break
        return ans, [(d, s, None) for d, s, _ in hits]


def evidence_recall(gold, got):
    g = {(d, s) for d, s in gold}
    r = {(d, s) for d, s, _ in got}
    return len(g & r) / len(g) if g else 1.0
