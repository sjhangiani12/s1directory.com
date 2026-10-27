"""List filings that have no entry yet (oldest first), and the cover art already in use.

  python site-src/tools/pending.py            # all pending filings
  python site-src/tools/pending.py --limit 20 # the next batch
  python site-src/tools/pending.py --art      # used AIC image_ids, one per line
"""
import argparse
import glob
import json
import os

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def entries():
    out = {}
    for p in sorted(glob.glob(os.path.join(SRC, "entries*.json"))):
        for x in json.load(open(p)):
            out[x["slug"]] = x
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--art", action="store_true")
    a = ap.parse_args()
    done = entries()
    if a.art:
        print("\n".join(sorted({x["cover"]["image_id"] for x in done.values() if x.get("cover", {}).get("image_id")})))
        return
    filings = json.load(open(os.path.join(SRC, "filings.json")))
    todo = sorted((f for f in filings if f["slug"] not in done), key=lambda f: f["date"])
    print(json.dumps(todo[:a.limit or None], indent=1))


if __name__ == "__main__":
    main()
