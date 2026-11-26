"""Pull real inputs from SEC EDGAR for the borrower screen. Run on your own machine
(EDGAR was not reachable from the build environment, so this was not executed there).

Step 1 - find candidate filers (prints a deduplicated list and saves data/edgar_raw/search_results.csv):
    python scripts/fetch_edgar.py --email you@gatech.edu --search "\"Total Net Leverage Ratio\" \"Compliance Certificate\""

Step 2 - download credit documents + XBRL facts for chosen CIKs:
    python scripts/fetch_edgar.py --email you@gatech.edu --cik 0001234567 0007654321 --limit 120

Writes data/edgar_raw/<cik>/: companyfacts.json (XBRL), submissions.json, and Exhibit 10 documents from
8-K / 10-Q / 10-K filings that look like a credit agreement or amendment, plus manifest.csv.
SEC fair-access policy: identify yourself in the User-Agent and stay under 10 requests/second.
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "edgar_raw"
CREDIT_RE = re.compile(rb"(?i)(credit agreement|loan agreement|amendment no\.|first amendment|second amendment|"
                       rb"third amendment|consolidated ebitda)")


def get(url, ua, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
            time.sleep(0.15)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < tries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise


def search(q, ua, pages=3):
    OUT.mkdir(parents=True, exist_ok=True)
    seen = {}
    for page in range(pages):
        url = ("https://efts.sec.gov/LATEST/search-index?q=" + urllib.parse.quote(q)
               + "&forms=8-K,10-Q,10-K&from=" + str(page * 100))
        try:
            hits = json.loads(get(url, ua))["hits"]["hits"]
        except Exception as e:  # noqa
            print("search request failed:", e)
            break
        if not hits:
            break
        for h in hits:
            s = h["_source"]
            for cik, name in zip(s.get("ciks", []), s.get("display_names", [])):
                d = seen.setdefault(cik, {"cik": cik, "name": name, "hits": 0, "latest": "", "forms": set()})
                d["hits"] += 1
                d["latest"] = max(d["latest"], s.get("file_date", ""))
                d["forms"].add(s.get("form", ""))
    rows = sorted(seen.values(), key=lambda d: -d["hits"])
    with open(OUT / "search_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cik", "name", "hits", "latest_filing", "forms"])
        for d in rows:
            w.writerow([d["cik"], d["name"], d["hits"], d["latest"], " ".join(sorted(d["forms"]))])
    print(f"{len(rows)} filers. Top 40 (full list in {OUT / 'search_results.csv'}):")
    for d in rows[:40]:
        print(f"  {d['cik']}  hits={d['hits']:3d}  latest={d['latest']}  {d['name'][:70]}")


def fetch_company(cik, ua, limit):
    cik10 = cik.zfill(10)
    d = OUT / cik10
    d.mkdir(parents=True, exist_ok=True)
    try:
        (d / "companyfacts.json").write_bytes(get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json", ua))
    except Exception as e:  # noqa
        print(f"  {cik10}: no XBRL company facts ({e})")
    subs = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik10}.json", ua))
    (d / "submissions.json").write_text(json.dumps(subs))
    rec = subs["filings"]["recent"]
    items = rec.get("items", [""] * len(rec["form"]))
    manifest, scanned, saved = [], 0, 0
    for form, acc, date, item in zip(rec["form"], rec["accessionNumber"], rec["filingDate"], items):
        if form not in ("8-K", "10-Q", "10-K"):
            continue
        # 8-Ks only when they report a material agreement (1.01) or a direct financial obligation (2.03)
        if form == "8-K" and not re.search(r"1\.01|2\.03", item or ""):
            continue
        if scanned >= limit:
            break
        scanned += 1
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{acc.replace('-', '')}"
        try:
            idx = json.loads(get(base + "/index.json", ua))
        except Exception:
            continue
        for it in idx["directory"]["item"]:
            name = it["name"].lower()
            if re.search(r"ex-?10|exhibit10|ex10", name) and name.endswith((".htm", ".html", ".txt")):
                try:
                    body = get(f"{base}/{it['name']}", ua)
                except Exception:
                    continue
                if CREDIT_RE.search(body[:30000]):
                    fn = f"{date}_{form}_{acc}_{it['name']}"
                    (d / fn).write_bytes(body)
                    manifest.append([date, form, acc, it["name"], fn])
                    saved += 1
    with open(d / "manifest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["filing_date", "form", "accession", "exhibit", "saved_as"])
        w.writerows(manifest)
    print(f"  {cik10} {subs.get('name', '')}: scanned {scanned} filings, saved {saved} credit documents -> {d}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True, help="your email, sent in the SEC User-Agent header")
    ap.add_argument("--search")
    ap.add_argument("--cik", nargs="*")
    ap.add_argument("--limit", type=int, default=120, help="max filings scanned per company")
    a = ap.parse_args()
    ua = f"GaTech MGT8803 covenant-monitoring project {a.email}"
    if not (a.search or a.cik):
        sys.exit("give --search and/or --cik")
    if a.search:
        search(a.search, ua)
    for c in a.cik or []:
        fetch_company(c, ua, a.limit)
