"""Pull real inputs from SEC EDGAR for the borrower screen (run on a laptop; EDGAR was not reachable
from the build environment, so this script is provided but was not executed there).

    python scripts/fetch_edgar.py --cik 0000320193 --email you@gatech.edu
    python scripts/fetch_edgar.py --search "\"Total Net Leverage Ratio\" \"Compliance Certificate\"" --email you@gatech.edu

Writes to data/edgar_raw/<cik>/: companyfacts.json (XBRL), submissions.json, and Exhibit 10 documents
from 8-K/10-Q/10-K filings whose description mentions a credit agreement or amendment.
SEC fair-access policy: identify yourself in the User-Agent and stay under 10 requests/second.
"""
import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "edgar_raw"


def get(url, ua):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
    time.sleep(0.15)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_company(cik, ua):
    cik10 = cik.zfill(10)
    d = OUT / cik10
    d.mkdir(parents=True, exist_ok=True)
    (d / "companyfacts.json").write_bytes(get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json", ua))
    subs = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik10}.json", ua))
    (d / "submissions.json").write_text(json.dumps(subs))
    rec = subs["filings"]["recent"]
    n = 0
    for form, acc, prim in zip(rec["form"], rec["accessionNumber"], rec["primaryDocument"]):
        if form not in ("8-K", "10-Q", "10-K"):
            continue
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{acc.replace('-', '')}"
        try:
            idx = json.loads(get(base + "/index.json", ua))
        except Exception:
            continue
        for item in idx["directory"]["item"]:
            name = item["name"].lower()
            if re.search(r"ex-?10", name) and name.endswith((".htm", ".html", ".txt")):
                body = get(f"{base}/{item['name']}", ua)
                if re.search(rb"(?i)credit agreement|amendment no\.|first amendment", body[:20000]):
                    (d / f"{acc}_{item['name']}").write_bytes(body)
                    n += 1
    print(f"{cik10}: {n} exhibit-10 credit documents saved to {d}")


def search(q, ua):
    url = "https://efts.sec.gov/LATEST/search-index?q=" + urllib.parse.quote(q) + "&forms=8-K,10-Q,10-K"
    hits = json.loads(get(url, ua))["hits"]["hits"]
    for h in hits[:50]:
        s = h["_source"]
        print(s.get("ciks"), s.get("display_names"), s.get("file_date"), s.get("form"))


if __name__ == "__main__":
    import urllib.parse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cik")
    ap.add_argument("--search")
    ap.add_argument("--email", required=True, help="contact email for the SEC User-Agent header")
    a = ap.parse_args()
    ua = f"GaTech MGT8803 covenant-monitoring project {a.email}"
    if a.search:
        search(a.search, ua)
    if a.cik:
        fetch_company(a.cik, ua)
