"""Find new tech IPOs on SEC EDGAR that are not in filings.json yet.

An IPO shows up on EDGAR as a 424B4 (the final, priced prospectus). For each 424B4 in the
date range, keep it when the company is in a tech SIC code, has no annual report (10-K / 20-F)
filed before it (so it was not public yet), and is not a SPAC or already in the directory.

  python site-src/tools/discover.py                     # since the newest filing in filings.json
  python site-src/tools/discover.py --since 2018-10-13 --until 2019-12-31
  python site-src/tools/discover.py --write             # also append the results to filings.json

Prints the candidates as JSON. The writer still decides if each one belongs (see ROUTINE.md).
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta

import threading
from concurrent.futures import ThreadPoolExecutor

import requests

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILINGS = os.path.join(SRC, "filings.json")
SKIPPED = os.path.join(SRC, "skipped.json")  # {cik: "name: reason"} for IPOs the writer rejected
UA = {"User-Agent": "S1Directory research bot https://www.s1directory.com"}

# SIC codes for software, internet, IT services, hardware, semis, telecom, e-commerce, fintech.
TECH_SIC = {
    "3570", "3571", "3572", "3575", "3576", "3577", "3578", "3579",
    "3661", "3663", "3669", "3670", "3672", "3674", "3677", "3678", "3679",
    "3823", "3825", "3826", "3829", "3841", "3845",
    "4812", "4813", "4822", "4899",
    "5045", "5961", "6199", "6211",
    "7370", "7371", "7372", "7373", "7374", "7375", "7376", "7377", "7378", "7379",
    "7389", "8742",
}
ANNUAL = {"10-K", "10-K405", "20-F", "40-F"}
REGISTRATION = ("S-1", "F-1", "SB-2", "S-1/A", "F-1/A")


CACHE = os.path.join(SRC, ".edgar-cache")
_lock, _last = threading.Lock(), [0.0]


def throttle(gap=0.12):
    with _lock:
        wait = _last[0] + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def get(url, **kw):
    err = None
    for i in range(6):
        try:
            throttle()
            r = requests.get(url, headers=UA, timeout=30, **kw)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                break
            err = f"HTTP {r.status_code}"
        except requests.RequestException as ex:
            err = ex
        time.sleep(2 + i * 3)
    raise RuntimeError(f"{url}: {err}")


def get_json(url):
    """Fetch JSON, caching it on disk so a rerun after a dropped connection resumes quickly."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9.]+", "_", url.split("//", 1)[1]) + ".json")
    if os.path.exists(path):
        return json.load(open(path))
    data = get(url).json()
    json.dump(data, open(path, "w"))
    return data


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def clean_name(s):
    s = re.sub(r"\s*\(.*$", "", s).strip().rstrip(",")
    if s.isupper():
        s = " ".join(w if len(w) <= 3 and w not in {"INC", "LTD", "THE", "AND"} else w.title() for w in s.split())
    return re.sub(r"[,.]", "", s).replace("  ", " ").strip()


def search_424b4(since, until):
    hits, start = [], 0
    while True:
        r = get("https://efts.sec.gov/LATEST/search-index",
                params={"forms": "424B4", "startdt": since, "enddt": until, "from": start}).json()
        page = r["hits"]["hits"]
        hits += page
        start += len(page)
        if not page or start >= r["hits"]["total"]["value"]:
            return hits


def all_filings(cik):
    sub = get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    rows = []
    blocks = [sub["filings"]["recent"]] + [get_json(f"https://data.sec.gov/submissions/{f['name']}")
                                           for f in sub["filings"].get("files", [])]
    for b in blocks:
        rows += zip(b["form"], b["filingDate"], b["accessionNumber"])
    return sub, rows


def head_text(url, limit=250_000):
    """First part of a document only. Prospectuses run 5-15 MB; the price is on the cover page."""
    for i in range(4):
        try:
            throttle()
            with requests.get(url, headers=UA, timeout=30, stream=True) as r:
                if r.status_code == 404:
                    return ""
                if r.status_code != 200:
                    raise requests.RequestException(f"HTTP {r.status_code}")
                buf = b""
                for chunk in r.iter_content(32_768):
                    buf += chunk
                    if len(buf) >= limit:
                        break
            return buf.decode("utf-8", "ignore")
        except requests.RequestException:
            time.sleep(2 + i * 3)
    return ""


def offer_price(cik, acc, doc):
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
    head = head_text(url)
    text = re.sub(r"<[^>]+>|&nbsp;|&#160;", " ", head)
    m = re.search(r"(?:initial public offering price|public offering price)[^$]{0,200}\$\s?(\d{1,4}\.\d{2})", text, re.I)
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--until", default=date.today().isoformat())
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    known = json.load(open(FILINGS))
    known_ciks = {re.search(r"/data/(\d+)/", f["s1"]).group(1) for f in known if "/data/" in f.get("s1", "")}
    known_slugs = {f["slug"] for f in known}
    if os.path.exists(SKIPPED):
        known_ciks |= {str(int(c)) for c in json.load(open(SKIPPED))}
    since = a.since or (datetime.strptime(max(f["date"] for f in known), "%Y%m%d") + timedelta(days=1)).date().isoformat()
    print(f"searching 424B4 filings {since} .. {a.until}", file=sys.stderr)

    # first 424B4 per company, tech sector codes only
    seen, todo = set(), []
    for h in sorted(search_424b4(since, a.until), key=lambda h: h["_source"]["file_date"]):
        cik = h["_source"]["ciks"][0]
        sic = (h["_source"].get("sics") or [""])[0]
        if cik in seen or sic not in TECH_SIC:
            continue
        seen.add(cik)
        if str(int(cik)) not in known_ciks:
            todo.append(h)
    print(f"checking {len(todo)} companies", file=sys.stderr, flush=True)

    def check(h):
        s = h["_source"]
        cik, sic, fdate = s["ciks"][0], (s.get("sics") or [""])[0], s["file_date"]
        sub, rows = all_filings(cik)
        if any(f in ANNUAL and d < fdate for f, d, _ in rows):
            return None  # already public before this prospectus: a follow-on, not an IPO
        regs = sorted((d, acc) for f, d, acc in rows if f in REGISTRATION[:3] and d <= fdate)
        if not regs:
            return None
        acc, doc = h["_id"].split(":")
        name = clean_name(sub.get("name") or s["display_names"][0])
        reg_acc = regs[0][1]
        return {
            "name": name,
            "slug": slugify(name),
            "date": fdate.replace("-", ""),
            "sic": sic,
            "ticker": (sub.get("tickers") or [None])[0],
            "price": offer_price(cik, acc, doc),
            "s1": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{reg_acc.replace('-', '')}/{reg_acc}-index.htm",
            "cik": str(int(cik)),
            "sic_description": sub.get("sicDescription"),
            "prospectus": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}",
        }

    out, done = [], 0
    with ThreadPoolExecutor(6) as pool:
        for r in pool.map(check, todo):
            done += 1
            if r and r["slug"] not in known_slugs:
                out.append(r)
                print(f"  + {r['name']} ({r['ticker']}) {r['date']} sic {r['sic']}", file=sys.stderr, flush=True)
            if done % 25 == 0:
                print(f"  . {done}/{len(todo)} checked, {len(out)} kept", file=sys.stderr, flush=True)

    print(json.dumps(out, indent=2))
    if a.write and out:
        keep = ("name", "slug", "date", "sic", "ticker", "price", "s1")
        known += [{k: x[k] for k in keep} for x in out]
        known.sort(key=lambda f: f["date"], reverse=True)
        json.dump(known, open(FILINGS, "w"), indent=1)
        print(f"wrote {len(out)} new filings to filings.json", file=sys.stderr)


if __name__ == "__main__":
    main()
