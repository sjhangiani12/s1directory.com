"""Merge writer output into filings.json and a new entries file, and report problems.

  python site-src/tools/merge_batch.py IN_DIR OUT_NAME   # reads IN_DIR/in*.json + IN_DIR/out*.json

For each written entry: takes the filing row from the input batch (or the entry's "filing" object for
manual rows), applies the entry's corrected price and ticker, and appends it to filings.json.
Entries go to site-src/OUT_NAME. Reports duplicate cover art and missing fields; it does not fix them.
"""
import glob
import json
import os
import re
import sys

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELDS = ("name", "slug", "date", "sic", "ticker", "price", "s1")


def main(in_dir, out_name):
    filings = json.load(open(os.path.join(SRC, "filings.json")))
    known = {f["slug"] for f in filings}
    used = {}
    for p in glob.glob(os.path.join(SRC, "entries*.json")):
        if os.path.basename(p) == out_name:
            continue
        for x in json.load(open(p)):
            used[x["cover"]["image_id"]] = x["slug"]

    rows, entries, problems = [], [], []
    for p in sorted(glob.glob(os.path.join(in_dir, "out*.json"))):
        inputs = {x["slug"]: x for x in json.load(open(p.replace("out", "in")))}
        for x in json.load(open(p)):
            src = inputs.get(x["slug"])
            if src is None:
                problems.append(f"{x['slug']}: not in its input batch")
                continue
            f = {k: src.get(k) for k in FIELDS}
            f.update({k: v for k, v in (x.pop("filing", None) or {}).items() if k in FIELDS and v})
            for k in ("price", "ticker", "date"):
                if x.get(k):
                    f[k] = x.pop(k)
            f["slug"] = x["slug"]
            if not f.get("s1") and src.get("cik"):
                f["s1"] = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={src['cik']}"
            missing = [k for k in FIELDS if not f.get(k)]
            if missing:
                problems.append(f"{x['slug']}: filing missing {missing}")
                continue
            if not re.match(r"^\d{8}$", str(f["date"])):
                problems.append(f"{x['slug']}: bad date {f['date']}")
                continue
            if f["slug"] in known:
                problems.append(f"{x['slug']}: already in filings.json")
                continue
            iid = x.get("cover", {}).get("image_id")
            if not iid:
                problems.append(f"{x['slug']}: no cover image_id")
            elif iid in used:
                problems.append(f"{x['slug']}: cover {iid} already used by {used[iid]}")
            else:
                used[iid] = x["slug"]
            f["price"] = float(f["price"])
            rows.append(f)
            entries.append(x)
            known.add(f["slug"])

    filings += rows
    filings.sort(key=lambda f: f["date"], reverse=True)
    json.dump(filings, open(os.path.join(SRC, "filings.json"), "w"), indent=1)
    json.dump(entries, open(os.path.join(SRC, out_name), "w"), indent=1, ensure_ascii=False)
    print(f"merged {len(entries)} entries into {out_name}; filings.json now has {len(filings)} rows")
    print("\n".join(problems) or "no problems")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
