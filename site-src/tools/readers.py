"""Convert every filing in filings.json into s1/<slug>/s1.json.gz for the S-1 reader.

  python site-src/tools/readers.py               # all filings that do not have one yet
  python site-src/tools/readers.py amazon-com-inc netflix-com-inc   # only these

Downloads are cached in site-src/.s1-cache, so a rerun only converts again.
"""
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1doc  # noqa: E402

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SRC)
lock = threading.Lock()


def convert(f):
    out = os.path.join(ROOT, "s1", f["slug"], "s1.json.gz")
    if "browse-edgar" in f["s1"]:
        return f["slug"], "no electronic S-1"
    try:
        doc = s1doc.build(f["s1"])
        if len(doc["html"]) < 20000:
            return f["slug"], f"too short ({len(doc['html'])} chars)"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        s1doc.write(doc, out)
        return f["slug"], None
    except Exception as ex:  # one bad filing must not stop the batch
        return f["slug"], str(ex)[:120]


def main(only):
    filings = json.load(open(os.path.join(SRC, "filings.json")))
    todo = [f for f in filings if (f["slug"] in only if only else
            not os.path.exists(os.path.join(ROOT, "s1", f["slug"], "s1.json.gz")))]
    print(f"converting {len(todo)} filings", flush=True)
    done, failed = 0, []
    with ThreadPoolExecutor(2) as pool:
        for slug, err in pool.map(convert, todo):
            done += 1
            if err:
                failed.append(f"{slug}: {err}")
            if done % 25 == 0:
                print(f"  {done}/{len(todo)} done, {len(failed)} failed", flush=True)
    print(f"finished: {done - len(failed)} converted, {len(failed)} failed", flush=True)
    print("\n".join(failed))


if __name__ == "__main__":
    main(set(sys.argv[1:]))
