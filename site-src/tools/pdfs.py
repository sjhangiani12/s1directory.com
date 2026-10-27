"""Print each converted S-1 to a PDF and upload it to R2 (served at files.s1directory.com/<slug>.pdf).

  python site-src/tools/pdfs.py                # every filing with s1.json.gz and no PDF yet
  python site-src/tools/pdfs.py --upload       # also upload new PDFs to the s1directory-files bucket
  python site-src/tools/pdfs.py amazon-com-inc # only these

PDFs are written to site-src/.pdf-cache (not committed). Each one opens with the book's cover and a
title page, then the cleaned filing text from the S-1 reader, set for print.
"""
import gzip
import html
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SRC)
OUT = os.path.join(SRC, ".pdf-cache")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BUCKET = "s1directory-files"

PRINT_CSS = """
@page { size: Letter; margin: 0.8in 0.85in; }
body { font: 10.5pt/1.55 "Newsreader", Georgia, serif; color: #1b1a18; }
.cover { height: 9.2in; display: flex; flex-direction: column; justify-content: space-between; page-break-after: always; }
.cover img { width: 4.2in; border-radius: 3pt; box-shadow: 0 6pt 18pt rgba(0,0,0,.25); }
.cover .k { font: 600 8pt "Paper Mono", ui-monospace, monospace; letter-spacing: .14em; text-transform: uppercase; color: #6b665d; }
.cover h1 { font: italic 400 44pt/1 "Newsreader", serif; margin: 10pt 0 6pt; }
.cover .m { font: 400 9pt "Paper Mono", ui-monospace, monospace; color: #6b665d; }
.cover .f { font: 400 8pt "Paper Mono", ui-monospace, monospace; color: #8a857c; border-top: .5pt solid #ccc; padding-top: 8pt; }
h2 { font: italic 400 20pt/1.15 "Newsreader", serif; margin: 22pt 0 8pt; page-break-after: avoid; }
h3 { font: 600 9pt/1.4 "Paper Mono", ui-monospace, monospace; margin: 14pt 0 6pt; page-break-after: avoid; }
p { margin: 0 0 7pt; orphans: 3; widows: 3; }
p.cv { text-align: center; font: 500 8pt/1.5 "Paper Mono", ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; color: #6b665d; margin: 0 0 4pt; }
table { border-collapse: collapse; font: 7.5pt/1.35 "Paper Mono", ui-monospace, monospace; margin: 8pt 0 12pt; width: 100%; page-break-inside: auto; }
tr { page-break-inside: avoid; }
td, th { padding: 2pt 4pt; border-bottom: .3pt solid #ddd; vertical-align: bottom; }
pre { font: 7.5pt/1.4 "Paper Mono", ui-monospace, monospace; white-space: pre-wrap; }
img { max-width: 100%; }
a { color: inherit; text-decoration: none; }
"""


def page_html(f, doc):
    cover = os.path.join(ROOT, "covers", f"{f['slug']}.jpg")
    font = os.path.join(SRC, "static", "PaperMono.woff2")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400..600;1,6..72,400&display=block" rel="stylesheet">
<style>@font-face {{ font-family: "Paper Mono"; src: url("file://{font}"); }}{PRINT_CSS}</style></head><body>
<section class="cover"><div><div class="k">Form S-1 &middot; Registration Statement</div>
<h1>{html.escape(f['name'])}</h1>
<div class="m">IPO priced {f['date'][:4]}-{f['date'][4:6]}-{f['date'][6:]}{f" &middot; ${f['price']:.2f} a share" if f.get('price') else ""}{f" &middot; {html.escape(f['ticker'])}" if f.get('ticker') else ""}</div></div>
{f'<img src="file://{cover}">' if os.path.exists(cover) else ""}
<div class="f">From S1 Directory &middot; www.s1directory.com/s1/{f['slug']}/ &middot; Source: {html.escape(doc['source'])}</div></section>
{doc['html']}</body></html>"""


def make(f):
    src = os.path.join(ROOT, "s1", f["slug"], "s1.json.gz")
    out = os.path.join(OUT, f"{f['slug']}.pdf")
    if os.path.exists(out):
        return f["slug"], None
    doc = json.load(gzip.open(src, "rt", encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "p.html")
        open(page, "w").write(page_html(f, doc))
        r = subprocess.run([CHROME, "--headless=new", f"--user-data-dir={tmp}/c", "--no-pdf-header-footer",
                            "--allow-file-access-from-files", "--virtual-time-budget=20000",
                            f"--print-to-pdf={out}", f"file://{page}"], capture_output=True, timeout=600)
    return f["slug"], None if os.path.exists(out) else f"chrome exit {r.returncode}"


def upload(slug):
    path = os.path.join(OUT, f"{slug}.pdf")
    r = subprocess.run(["npx", "-y", "wrangler@4", "r2", "object", "put", f"{BUCKET}/{slug}.pdf", "--file", path,
                        "--content-type", "application/pdf", "--cache-control", "public, max-age=86400", "--remote"],
                       capture_output=True, text=True, cwd=tempfile.gettempdir())
    return slug, None if r.returncode == 0 else r.stderr[-200:]


def main(args):
    os.makedirs(OUT, exist_ok=True)
    only = {a for a in args if not a.startswith("--")}
    filings = [f for f in json.load(open(os.path.join(SRC, "filings.json")))
               if os.path.exists(os.path.join(ROOT, "s1", f["slug"], "s1.json.gz")) and (not only or f["slug"] in only)]
    print(f"printing {len(filings)} PDFs", flush=True)
    failed = []
    with ThreadPoolExecutor(4) as pool:
        for i, (slug, err) in enumerate(pool.map(make, filings), 1):
            if err:
                failed.append(f"{slug}: {err}")
            if i % 25 == 0:
                print(f"  {i}/{len(filings)} printed, {len(failed)} failed", flush=True)
    if "--upload" in args:
        done_file = os.path.join(OUT, "uploaded.txt")
        done = set(open(done_file).read().split()) if os.path.exists(done_file) else set()
        todo = [f["slug"] for f in filings if f["slug"] not in done and os.path.exists(os.path.join(OUT, f"{f['slug']}.pdf"))]
        print(f"uploading {len(todo)} PDFs", flush=True)
        with ThreadPoolExecutor(4) as pool, open(done_file, "a") as log:
            for i, (slug, err) in enumerate(pool.map(upload, todo), 1):
                if err:
                    failed.append(f"upload {slug}: {err}")
                else:
                    log.write(slug + "\n"); log.flush()
                if i % 25 == 0:
                    print(f"  {i}/{len(todo)} uploaded", flush=True)
    print(f"finished, {len(failed)} failed", flush=True)
    print("\n".join(failed))


if __name__ == "__main__":
    main(sys.argv[1:])
