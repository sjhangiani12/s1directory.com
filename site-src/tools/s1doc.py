"""Download an S-1 from EDGAR and turn it into clean, readable HTML for the S-1 reader.

  python site-src/tools/s1doc.py <index-url> out.json.gz      # one filing (for testing)

The output is gzip-compressed JSON: {"html": ..., "toc": [[id, text, level], ...], "source": url}.
GitHub Pages serves it as a file; the reader page unpacks it in the browser. Compressed, a filing is
about a fifth of its raw size, which keeps the whole library inside the Pages size limit.
"""
import gzip
import hashlib
import json
import os
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(SRC, ".s1-cache")
UA = {"User-Agent": "S1Directory research bot https://www.s1directory.com"}
REG_TYPES = ("S-1", "F-1", "SB-2", "S-1/A", "F-1/A")
KEEP_ATTRS = {"a": {"href", "id", "name"}, "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"},
              "img": {"src", "alt", "width", "height"}}
PAGE_NO = re.compile(r"^\s*(?:page\s+)?(?:\d{1,3}|[ivxlc]{1,6}|[A-Z]-\d{1,3}|F-\d{1,3}|II-\d{1,3})\s*$", re.I)


def fetch(url):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest()[:20])
    if os.path.exists(path):
        return open(path, "rb").read()
    for i in range(5):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200:
                open(path, "wb").write(r.content)
                time.sleep(0.12)
                return r.content
            if r.status_code == 404:
                break
        except requests.RequestException:
            pass
        time.sleep(2 + 3 * i)
    raise RuntimeError(f"could not fetch {url}")


def main_document(index_url):
    """The registration statement itself, from a filing index page. Returns (url, is_text)."""
    soup = BeautifulSoup(fetch(index_url), "lxml")
    rows = []
    for tr in soup.select("table.tableFile tr"):
        tds = tr.find_all("td")
        if len(tds) >= 4 and tds[2].a:
            rows.append((tds[3].get_text(strip=True), urljoin(index_url, tds[2].a["href"])))
    for kind, href in rows:
        if kind in REG_TYPES and re.search(r"\.(?:htm|html|txt)$", href):
            return href.replace("/ix?doc=", ""), href.endswith(".txt")
    # old filings link only the folder: use the complete submission text file beside the index
    return re.sub(r"-index\.html?$", ".txt", index_url), True


def text_from_submission(raw):
    """Pull the registration statement out of a complete-submission .txt file."""
    raw = raw.decode("latin-1")
    for doc in re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", raw, re.S | re.I) or [raw]:
        kind = re.search(r"<TYPE>\s*([^\s<]+)", doc, re.I)
        if kind and kind.group(1).upper() not in REG_TYPES:
            continue
        body = re.search(r"<TEXT>(.*)", doc, re.S | re.I)
        return body.group(1) if body else doc
    return raw


# ---------- plain-text filings (mostly 1990s) ----------
def text_to_html(text):
    out, toc = [], []
    text = re.sub(r"<PAGE>\s*\d*", "\n\n", text, flags=re.I)
    text = re.sub(r"</?(?:CAPTION|S|C|FN|R|TABLE)>", "", text, flags=re.I)
    for block in re.split(r"\n\s*\n", text):
        lines = [l.rstrip() for l in block.strip("\n").splitlines() if l.strip() and not re.match(r"^[\s=_\-*]+$", l)]
        if not lines:
            continue
        joined = " ".join(l.strip() for l in lines)
        if len(lines) == 1 and PAGE_NO.match(joined):
            continue
        tabular = sum(bool(re.search(r"\S\s{3,}\S", l)) for l in lines) >= max(2, len(lines) // 2)
        if tabular:
            out.append("<pre>" + html_escape("\n".join(lines)) + "</pre>")
        elif len(lines) <= 2 and len(joined) < 90 and joined.upper() == joined and re.search(r"[A-Z]{3}", joined):
            hid = f"s{len(toc) + 1}"
            toc.append([hid, title(joined), 2])
            out.append(f'<h2 id="{hid}">{html_escape(title(joined))}</h2>')
        else:
            out.append("<p>" + html_escape(re.sub(r"\s+", " ", joined)) + "</p>")
    start = trim_toc(toc)
    if start is not toc and start:
        cut = out.index(next(o for o in out if f'id="{start[0][0]}"' in o))
        out[:cut] = [re.sub(r"^<(h2|p)[^>]*>(.*)</\1>$", r'<p class="cv">\2</p>', o, flags=re.S) for o in out[:cut]]
    return "\n".join(out), start


SMALL = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with", "from"}


def title(s):
    """Title case that leaves "Management's" and "Amazon.com" alone and keeps small words small."""
    words = s.lower().split(" ")
    out = []
    for i, w in enumerate(words):
        if i and w in SMALL:
            out.append(w)
        else:
            out.append(re.sub(r"^([^a-z]*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), w))
    return " ".join(out)


def html_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------- HTML filings ----------
def is_bold(el):
    style = (el.get("style") or "").replace(" ", "").lower()
    if "font-weight:bold" in style or "font-weight:700" in style:
        return True
    texts = [t for t in el.find_all(string=True) if t.strip()]
    if not texts:
        return False
    def bold(t):
        for p in t.parents:
            if p is el:
                return False
            if p.name in ("b", "strong"):
                return True
            st = (p.get("style") or "").replace(" ", "").lower()
            if "font-weight:bold" in st or "font-weight:700" in st:
                return True
        return False
    return all(bold(t) for t in texts)


def clean_table(table):
    rows = table.find_all("tr")
    for tr in rows:
        cells = tr.find_all(["td", "th"], recursive=False)
        for i, c in enumerate(cells):  # "$" "(" belong to the next cell, ")" "%" to the previous one
            t = c.get_text(strip=True)
            if t in ("$", "(", "$(") and i + 1 < len(cells):
                nxt = cells[i + 1]
                nxt.insert(0, NavigableString(t))
                c.clear()
            elif t in (")", "%", ")%", "%)") and i > 0:
                cells[i - 1].append(NavigableString(t))
                c.clear()
    # drop columns that are empty in every row (SEC tables use many spacer cells)
    grid = []
    for tr in rows:
        col, line = 0, []
        for c in tr.find_all(["td", "th"], recursive=False):
            span = int(c.get("colspan", 1) or 1) if str(c.get("colspan", 1)).isdigit() else 1
            line.append((col, span, c))
            col += span
        grid.append(line)
    width = max((s + n for line in grid for s, n, _ in line), default=0)
    used = [False] * width
    for line in grid:
        for s, n, c in line:
            if c.get_text(strip=True):
                for k in range(s, s + n):
                    used[k] = True
    for line in grid:
        for s, n, c in line:
            keep = sum(used[s:s + n])
            if keep == 0:
                c.decompose()
            elif keep != n:
                c["colspan"] = str(keep)
    for tr in rows:
        if not tr.get_text(strip=True):
            tr.decompose()
    if not table.get_text(strip=True):
        table.decompose()


ENVELOPE = re.compile(r"</?(?:document|type|sequence|filename|description|text)>[^<\n]*", re.I)
TOC_START = re.compile(r"summary|table of contents|the offering|risk factors|our company|overview", re.I)


def trim_toc(toc):
    """The cover page is full of bold lines ("United States", "Form S-1"); start contents at the body."""
    for i, t in enumerate(toc):
        if TOC_START.search(t[1]):
            return toc[i:]
    return toc


ENDS = re.compile(r"[.!?:;\u2014][\"\u201d\u2019)\]]*\s*$|[\u00a3\u2610\u2612\u25a1\u25a0\u2022]\s*$")


def join_lines(body):
    """Some filing tools place every printed line in its own box, so a sentence arrives as several
    paragraphs. Join a paragraph to the next one while it ends mid-sentence."""
    for p in body.find_all("p"):
        if p.parent is None or p.get("class"):
            continue
        while True:
            nxt = p.find_next_sibling()
            text = p.get_text(" ", strip=True)
            if nxt is None or nxt.name != "p" or nxt.get("class") or len(text) < 20 or ENDS.search(text):
                break
            between = p.next_sibling
            if between is not nxt and str(between).strip():
                break
            p.append(" ")
            for child in list(nxt.contents):
                p.append(child)
            nxt.decompose()


def html_to_clean(raw, base_url):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    raw = ENVELOPE.sub("", raw)
    soup = BeautifulSoup(raw, "lxml")
    body = soup.body or soup
    for t in body.find_all(["script", "style", "head", "title", "meta", "link"]):
        t.decompose()
    for t in body.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        t.decompose()
    for t in body.find_all(re.compile(r"^ix:header$", re.I)):
        t.decompose()

    # the filing's own table of contents, when it links to anchors in the document, is the best map
    doc_toc, ids = [], {}
    for a in body.find_all("a", href=True):
        h = a["href"]
        t = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        if not h.startswith("#") or h[1:] in ids or not t or len(t) > 120 or PAGE_NO.match(t) \
                or not re.search(r"[A-Za-z]{3}", t):
            continue
        tgt = body.find(id=h[1:]) or body.find(attrs={"name": h[1:]})
        if tgt is None:
            continue
        hid = f"t{len(doc_toc) + 1}"
        ids[h[1:]] = hid
        label = title(t) if t.upper() == t else t
        head = soup.new_tag("h2", id=hid)
        head.string = label
        if re.sub(r"\W", "", tgt.get_text()).lower() == re.sub(r"\W", "", t).lower():
            tgt.replace_with(head)
        else:
            tgt.insert_before(head)
        doc_toc.append([hid, label, 2])
    order = {h.get("id"): i for i, h in enumerate(body.find_all("h2"))}
    doc_toc = sorted((t for t in doc_toc if len(t[1]) >= 8 and not re.match(r"^table of", t[1], re.I)),
                     key=lambda t: order.get(t[0], 1 << 30))
    if len(doc_toc) >= 5:
        for a in body.find_all("a", href=True):
            if a["href"][1:] in ids:
                a["href"] = "#" + ids[a["href"][1:]]
    else:
        doc_toc = []

    # headings: short, all-bold blocks
    toc, nh = [], 0
    for el in body.find_all(["p", "div"]):
        if el.find(["p", "div", "table", "h2"]):
            continue
        text = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if not (3 <= len(text) < 110) or text.endswith((".", ",", ";", ":")) or PAGE_NO.match(text):
            continue
        if is_bold(el):
            level = 2 if text.upper() == text and re.search(r"[A-Z]{3}", text) else 3
            el.name = f"h{level}"
            el.attrs = {}
            el.clear()
            el.append(title(text) if level == 2 else text)
            nh += 1
            hid = f"s{nh}"
            el["id"] = hid
            if level == 2:
                toc.append([hid, el.get_text(), 2])

    start = doc_toc or trim_toc(toc)
    start_id = start[0][0] if start and (doc_toc or start is not toc or TOC_START.search(start[0][1])) else None
    if start_id:
        for h in body.find_all(["h2", "h3"]):
            if h.get("id") == start_id:
                break
            if h.name == "h2" and h.get("id", "").startswith("t"):
                continue
            h.name, h.attrs = "p", {"class": "cv"}
    for t in body.find_all(["font", "span", "center", "u", "ix:nonnumeric", "ix:nonfraction", "ix:continuation"]):
        t.unwrap()
    for t in body.find_all(re.compile(r"^ix:", re.I)):
        t.unwrap()
    for t in body.find_all("b"):
        t.name = "strong"
    for t in body.find_all("i"):
        t.name = "em"
    for t in body.find_all("hr"):
        t.decompose()
    for t in body.find_all("img"):
        t["src"] = urljoin(base_url, t.get("src", ""))
        t["loading"] = "lazy"
    for t in body.find_all("table"):
        clean_table(t)
    for t in body.find_all(["p", "div"]):
        text = t.get_text(" ", strip=True)
        if (not text and not t.find("img")) or PAGE_NO.match(text or "x"):
            t.decompose()
        elif t.name == "div" and not t.find(["p", "div", "table", "h2", "h3", "ul", "ol"]):
            t.name = "p"
    for t in body.find_all(True):
        allowed = KEEP_ATTRS.get(t.name, {"id"} if t.name in ("h2", "h3") else {"class"} if t.get("class") in (["cv"], "cv") else set())
        if t.name == "img":
            allowed = KEEP_ATTRS["img"] | {"loading"}
        t.attrs = {k: v for k, v in t.attrs.items() if k in allowed}
    for t in body.find_all("div"):
        t.unwrap()
    # running page headers ("Table of Contents" back-links) and headings repeated under their own title
    flat = lambda el: re.sub(r"[^a-z0-9]", "", el.get_text().lower())
    toc_ids = {t[0] for t in (doc_toc or toc)}
    for el in body.find_all(["h2", "h3", "p"]):
        if el.parent is not None and flat(el) == "tableofcontents" and el.get("id") not in toc_ids:
            el.decompose()
    for h in body.find_all("h2"):
        nxt = h.find_next_sibling()
        while nxt is not None and nxt.name in ("h3", "p") and flat(nxt) == flat(h):
            gone, nxt = nxt, nxt.find_next_sibling()
            gone.decompose()
    join_lines(body)
    html = "".join(str(c) for c in body.contents)
    html = re.sub(r"[ \t]{2,}", " ", html)
    html = re.sub(r"(?:&nbsp;|\xa0)+", " ", html)
    html = re.sub(r"\n{2,}", "\n", html)
    return html, (doc_toc or trim_toc(toc))


def build(index_url):
    url, is_text = main_document(index_url)
    raw = fetch(url)
    if is_text:
        body = text_from_submission(raw)
        if re.search(r"<(?:html|body|p|div|font)[\s>]", body[:20000], re.I):
            html, toc = html_to_clean(body, url)
        else:
            html, toc = text_to_html(body)
    else:
        html, toc = html_to_clean(raw, url)
    return {"html": html, "toc": toc, "source": url}


def write(doc, out):
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    doc = build(sys.argv[1])
    write(doc, sys.argv[2])
    print(len(doc["html"]), "chars html,", os.path.getsize(sys.argv[2]), "bytes gz,", len(doc["toc"]), "toc entries")
