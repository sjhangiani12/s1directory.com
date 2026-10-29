"""Scan every converted S-1 for reading problems and print counts per problem, plus the worst filings.

  python site-src/tools/qa_readers.py            # summary
  python site-src/tools/qa_readers.py -v airbnb-inc   # show examples for one filing

Problems checked:
  toc_stamp     "Table of Contents" back-links left from page headers
  split         a paragraph ends mid-sentence and the next paragraph starts in lowercase
  spaced_head   letter-spaced headings such as "P rospectus Summar y"
  br_run        runs of <br> between blocks (page-break gaps)
  empty_block   empty paragraphs or headings
"""
import glob
import gzip
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAG = re.compile(r"<[^>]+>")
ENDS = re.compile(r"[.!?:;—][\"”’)\]]*\s*$|[£☐☒□■•]\s*$")


def text(s):
    return re.sub(r"\s+", " ", TAG.sub(" ", s)).strip()


def check(html):
    found = {}
    found["toc_stamp"] = [m.start() for m in re.finditer(r">\s*Table of Contents\s*<", html)]
    prose = re.sub(r"<table.*?</table>", "", html, flags=re.S)  # data tables are not prose
    blocks = re.findall(r"<(p|h[1-6])(?: [^>]*)?>(.*?)</\1>", prose, re.S)
    split = []
    for (t1, a), (t2, b) in zip(blocks, blocks[1:]):
        ta, tb = text(a), text(b)
        if t1 == "p" and t2 == "p" and len(ta) > 40 and not ENDS.search(ta) and re.match(r"^[a-z]", tb):
            split.append(f"…{ta[-50:]} ‖ {tb[:50]}…")
    found["split"] = split
    found["spaced_head"] = [text(b) for t, b in blocks if t.startswith("h") and re.search(r"\b[A-Z] [a-z]{2,}|[a-z] [a-z]\b(?= |$)", text(b))
                            and re.search(r"\b\w \w{2,} \w\b|\b[A-Z] [a-z]{3,}", text(b))]
    found["br_run"] = re.findall(r"(?:<br/?>\s*){2,}", html)
    found["empty_block"] = [t for t, b in blocks if not text(b) and "<img" not in b]
    return found


def main(args):
    verbose = "-v" in args
    only = [a for a in args if not a.startswith("-")]
    totals, worst = Counter(), Counter()
    for path in sorted(glob.glob(os.path.join(ROOT, "s1", "*", "s1.json.gz"))):
        slug = path.split(os.sep)[-2]
        if only and slug not in only:
            continue
        html = json.load(gzip.open(path, "rt", encoding="utf-8"))["html"]
        found = check(html)
        for k, v in found.items():
            totals[k] += len(v)
            worst[slug] += len(v) if k != "empty_block" else 0
        if verbose:
            for k, v in found.items():
                print(f"{slug} {k}: {len(v)}")
                for x in v[:6]:
                    print("    ", x if isinstance(x, str) else x)
    print("totals:", dict(totals))
    print("worst:", worst.most_common(8))


if __name__ == "__main__":
    main(sys.argv[1:])
