"""Build the static S1 Directory site into the repo root.

Run from the repo root:  .venv/bin/python site-src/build.py [--covers]
--covers re-renders every cover image (otherwise only missing ones are made).
"""
import glob, html, json, os, re, shutil, sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))
import treat
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "site-src")
CACHE = os.path.join(SRC, ".art-cache")
SITE = "https://www.s1directory.com"
FORCE = "--covers" in sys.argv

# Books that lead the 3d shelf on the home page, in order. Missing slugs are skipped.
SHELF = [
    "amazon-com-inc", "netflix-com-inc", "ebay-inc", "facebook-inc", "snap-inc", "dropbox-inc",
    "linkedin-corp", "juniper-networks", "akamai-technologies-inc", "zillow-inc", "etsy-inc",
    "box-inc", "roku-inc", "yelp-inc", "servicenow-inc", "f5-networks-inc", "verisign-inc",
    "kayak-software-corp", "wayfair-inc", "grubhub-inc", "elastic-nv", "redfin-corp",
    "broadcom-corp", "ariba-inc", "opentable-inc", "mercadolibre-inc",
]

e = html.escape


def load():
    filings = json.load(open(os.path.join(SRC, "filings.json")))
    entries = {}
    for p in sorted(glob.glob(os.path.join(SRC, "entries*.json"))):
        for x in json.load(open(p)):
            entries[x["slug"]] = x
    out = []
    for f in filings:
        x = entries.get(f["slug"])
        if not x or not x.get("cover", {}).get("image_id"):
            continue
        d = datetime.strptime(f["date"], "%Y%m%d")
        out.append({**f, **x, "dt": d})
    return out


def rgba(hx, a):
    hx = hx.lstrip("#")
    r, g, b = (int(hx[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"


def tags(b):
    dec = f"{b['dt'].year // 10 * 10}s"
    return f"{dec} {slugify(b['space'])}"


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def cover_html(b, size="sm", lazy=True, cls="cover"):
    c = b["cover"]
    n = len(b["display"])
    tcls = "title xlong" if n > 16 else "title long" if n > 10 else "title"
    img = f"/covers/{'sm/' if size == 'sm' else ''}{b['slug']}.jpg"
    style = f"--c-ink:{c['ink']};--c-paper:{c['paper']};--c-ink-a:{rgba(c['ink'], .72)}"
    return (
        f'<div class="{cls}" style="{style}" role="img" aria-label="Cover for {e(b["display"])}: {e(c.get("artwork") or "")}">'
        f'<img class="bg" src="{img}" alt="" {"loading=lazy " if lazy else ""}decoding="async">'
        f'<div class="scrim"></div>'
        f'<div class="ct top"><div class="kicker">S-1 &middot; {b["dt"].year}</div></div>'
        f'<div class="ct bot"><div class="{tcls}">{e(b["display"])}</div>'
        f'<div class="sub"><span>{e(b["ticker"])}</span><span>${b["price"]:.2f}</span></div></div>'
        f"</div>"
    )


def book3d_html(b):
    c = b["cover"]
    return (
        f'<a class="book3d" href="/s1/{b["slug"]}/" aria-label="{e(b["display"])}">'
        f'<div class="rot"><div class="lift">'
        f'<div class="face top"></div>'
        f'<div class="face spine" style="background:{c["accent"]}"><span class="t">{e(b["display"])}<small>{e(b["ticker"])}</small></span><span class="yr">{b["dt"].year}</span></div>'
        f'<div class="face front" style="background-image:url(/covers/sm/{b["slug"]}.jpg)"></div>'
        f"</div></div></a>"
    )


LOGO = (
    '<svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="20" fill="#1b1a18"/>'
    '<g fill="none" stroke="#f1efeb" stroke-width="1.6" stroke-linecap="round">'
    '<path d="M20 13.5c-2.6-1.9-5.8-2.3-9-1.6v14.5c3.2-.7 6.4-.3 9 1.6 2.6-1.9 5.8-2.3 9-1.6V11.9c-3.2-.7-6.4-.3-9 1.6z"/>'
    '<path d="M20 13.5V28"/></g></svg>'
)


def page(title, body, desc, current="", body_cls="", body_attrs="", canonical="/", og_image="/covers/amazon-com-inc.jpg"):
    nav_items = [("Library", "/#library"), ("Directory", "/directory/"), ("About", "/about/")]
    links = "".join(
        f'<a href="{href}"{" aria-current=page" if name == current else ""}>{name}</a>' for name, href in nav_items
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}{canonical}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{SITE}{og_image}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..500;1,6..72,300..500&display=swap" rel="stylesheet">
<link rel="preload" href="/assets/PaperMono.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/style.css?v={VERSION}">
</head>
<body class="{body_cls}" {body_attrs}>
<nav class="nav">
  <a class="mark" href="/">{LOGO}<span>S1 Directory</span></a>
  <div class="links">{links}</div>
  <div class="right"><a href="https://github.com/sjhangiani12/s1directory.com">GitHub</a></div>
</nav>
{body}
<footer><span>S1 Directory &middot; The founding documents of the internet.</span><span>Filings from <a href="https://www.sec.gov/edgar">SEC EDGAR</a>. Cover art from the <a href="https://www.artic.edu/open-access">Art Institute of Chicago</a> (CC0).</span></footer>
<script src="/assets/app.js?v={VERSION}" defer></script>
</body>
</html>
"""


def filters_html(books, top_n=5):
    counts = {}
    for b in books:
        counts[b["space"]] = counts.get(b["space"], 0) + 1
    spaces = sorted(counts, key=lambda s: -counts[s])[:top_n]
    pills = ['<button class="pill" data-f="all" aria-pressed="true">All S-1s</button>']
    pills += [f'<button class="pill" data-f="{d}" aria-pressed="false">{d}</button>' for d in ("1990s", "2000s", "2010s")]
    pills += [f'<button class="pill" data-f="{slugify(s)}" aria-pressed="false">{e(s)}</button>' for s in spaces]
    pills.append('<input class="search" type="search" placeholder="Search companies, tickers&hellip;" aria-label="Search">')
    return f'<div class="pills">{"".join(pills)}</div>'


def qstr(b):
    return e(" ".join([b["display"], b["name"], b["ticker"], b["space"] or "", str(b["dt"].year)]).lower())


def build_home(books):
    by = {b["slug"]: b for b in books}
    shelf = [by[s] for s in SHELF if s in by]
    shelf += [b for b in books if b not in shelf][: max(0, 26 - len(shelf))]
    cards = "".join(
        f'<a class="card" href="/s1/{b["slug"]}/" data-filter-item data-tags="{tags(b)}" data-q="{qstr(b)}">'
        f'{cover_html(b)}<div class="meta"><b>{e(b["display"])}</b><span>{e(b["space"])} &middot; {b["dt"].year}</span></div></a>'
        for b in books
    )
    years = f'{min(b["dt"].year for b in books)}&ndash;{max(b["dt"].year for b in books)}'
    body = f"""
<header class="hero">
  <h1 class="rise">The <em>Everyone Round</em></h1>
  <p class="rise d1">An IPO is the one round anyone can join. These are the S-1s that opened the door, bound and shelved.</p>
</header>
<section class="shelf rise d2" aria-label="Featured S-1s">
  <div class="shelf-track">{"".join(book3d_html(b) for b in shelf)}</div>
</section>
<section class="wrap" id="library">
  <div class="head"><h2>The Library</h2><div class="brace">&#123; {len(books)} S-1 filings, {years} &#125;</div></div>
  {filters_html(books)}
  <div class="grid">{cards}</div>
  <div class="empty">No S-1s match that search.</div>
</section>
"""
    return page("S1 Directory — The founding documents of the internet", body,
                f"A library of {len(books)} S-1 filings from the companies that built the internet, {html.unescape(years)}.")


def build_directory(books):
    rows = "".join(
        f'<div class="row" data-filter-item data-tags="{tags(b)}" data-q="{qstr(b)}">'
        f'<div class="nm"><img src="/covers/sm/{b["slug"]}.jpg" alt="" loading="lazy" width="38" height="51">'
        f'<span><a href="/s1/{b["slug"]}/">{e(b["display"])}</a> <small>({e(b["ticker"])})</small></span></div>'
        f'<div class="dk">{e(b["dek"])}</div>'
        f'<div class="rt"><a href="{e(b["s1"])}" target="_blank" rel="noopener">Read the S-1 &rarr;</a><span>{b["dt"]:%B} {b["dt"].day}, {b["dt"].year}</span></div>'
        f"</div>"
        for b in books
    )
    body = f"""
<section class="wrap">
  <div class="head"><h1>The Directory</h1><div class="brace">&#123; Every filing, from {books[-1]["display"]} to {books[0]["display"]} &#125;</div></div>
  {filters_html(books)}
  <div class="list">{rows}</div>
  <div class="empty">No S-1s match that search.</div>
  <button class="more">See more</button>
</section>
"""
    return page("Directory — S1 Directory", body, "Every S-1 in the library, with links to the original filing on SEC EDGAR.",
                current="Directory", body_attrs='data-page-size="30"', canonical="/directory/")


def build_article(b, prev, nxt):
    c = b["cover"]
    dl = [("Space", e(b["space"]))]
    if b.get("founders"):
        dl.append(("Founders", "<br>".join(e(f) for f in b["founders"])))
    ms = []
    if b.get("founded"):
        ms.append(f"Founded {b['founded']}")
    ms.append(f"IPO {b['dt']:%b} {b['dt'].day}, {b['dt'].year} at ${b['price']:.2f}")
    if b.get("fate"):
        ms.append(e(b["fate"]))
    dl.append(("Milestones", "<br>".join(ms)))
    dl.append(("Ticker", e(b["ticker"])))
    if b.get("hq"):
        dl.append(("Headquarters", e(b["hq"])))
    dl.append(("Links", f'<a href="{e(b["s1"])}" target="_blank" rel="noopener">S-1 on SEC EDGAR</a>'
                        f'<a href="https://www.artic.edu/artworks/{c.get("aic_id")}" target="_blank" rel="noopener">Cover artwork</a>'))
    dl_html = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in dl)

    secs = "".join(f"<h3>{e(s['heading'])}</h3><p>{e(s['body'])}</p>" for s in b.get("sections", []))
    pager = ""
    if prev:
        pager += f'<a href="/s1/{prev["slug"]}/">&larr; Newer<b>{e(prev["display"])}</b></a>'
    else:
        pager += "<span></span>"
    if nxt:
        pager += f'<a href="/s1/{nxt["slug"]}/">Older &rarr;<b>{e(nxt["display"])}</b></a>'

    body = f"""
<div class="doc">
  <aside class="l"><h1>{e(b["display"])}</h1><dl>{dl_html}</dl></aside>
  <main>
    <div class="ttl"><h2>{e(b["tagline"])}</h2>
      <div class="polaroids" aria-hidden="true"><div style="background-image:url(/covers/art/{b['slug']}.jpg)"></div><div style="background-image:url(/covers/sm/{b['slug']}.jpg)"></div><div style="background-image:url(/covers/crop/{b['slug']}.jpg)"></div></div>
    </div>
    <div class="date">Priced {b["dt"]:%B} {b["dt"].day:02d}, {b["dt"].year}</div>
    <article class="prose">
      <p class="lede">{e(b["lede"])}</p>
      {secs}
      <p class="credit">Cover: <a href="https://www.artic.edu/artworks/{c.get("aic_id")}" target="_blank" rel="noopener"><em>{e(c.get("artwork") or "")}</em></a>{", " + e(c["artist"]) if c.get("artist") else ""}. Art Institute of Chicago, public domain. Chosen for {e(c.get("theme") or "the story")}.</p>
    </article>
    <nav class="pager">{pager}</nav>
  </main>
  <aside class="r"><div class="sticky">{cover_html(b, size="lg", lazy=False)}
    <a class="cta" href="{e(b["s1"])}" target="_blank" rel="noopener">Read the original S-1 &rarr;</a></div></aside>
</div>
"""
    return page(f"{b['display']} S-1 ({b['dt'].year}) — S1 Directory", body, b["dek"], body_cls="article",
                canonical=f"/s1/{b['slug']}/", og_image=f"/covers/{b['slug']}.jpg")


def build_about(books):
    body = f"""
<section class="about">
  <h1>About</h1>
  <p>An S-1 is the document a company files with the SEC before it goes public. It is the most honest thing most companies ever write about themselves: what they do, how they make money, and what could go wrong.</p>
  <p>S1 Directory collects {len(books)} of them, from the companies that built the commercial internet. Each one is bound as a book, with a cover made from a public-domain artwork chosen for its story.</p>
  <p>Filings link to the original documents on <a href="https://www.sec.gov/edgar">SEC EDGAR</a>. IPO dates and offer prices come from the <a href="https://site.warrington.ufl.edu/ritter/ipo-data/">Jay Ritter IPO dataset</a> and sec-api.io. Cover art comes from the <a href="https://www.artic.edu/open-access">Art Institute of Chicago</a> open access collection (CC0). The company essays are short summaries. If you spot an error, <a href="https://github.com/sjhangiani12/s1directory.com/issues">open an issue</a>.</p>
</section>
"""
    return page("About — S1 Directory", body, "What S1 Directory is and where the data comes from.", current="About", canonical="/about/")


def render_covers(books):
    for d in ("covers", "covers/sm", "covers/art", "covers/crop"):
        os.makedirs(os.path.join(ROOT, d), exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)
    man_path = os.path.join(SRC, "covers-manifest.json")
    manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
    for i, b in enumerate(books):
        c = b["cover"]
        lg = os.path.join(ROOT, "covers", f"{b['slug']}.jpg")
        key = "|".join(str(c.get(k)) for k in ("image_id", "ink", "paper", "accent", "focus"))
        if os.path.exists(lg) and manifest.get(b["slug"]) == key and not FORCE:
            continue
        try:
            treat.make(c["image_id"], c["ink"], c["paper"], c["accent"], lg, CACHE, focus=c.get("focus"))
        except Exception as ex:  # noqa: BLE001
            print("cover failed", b["slug"], ex)
            continue
        im = Image.open(lg)
        im.resize((360, 480), Image.LANCZOS).save(os.path.join(ROOT, "covers/sm", f"{b['slug']}.jpg"), quality=80, optimize=True, progressive=True)
        im.crop((180, 300, 540, 780)).resize((180, 240), Image.LANCZOS).save(os.path.join(ROOT, "covers/crop", f"{b['slug']}.jpg"), quality=80)
        src = treat.cover_crop(Image.open(os.path.join(CACHE, f"{c['image_id']}.jpg")).convert("RGB"), c.get("focus"))
        src.resize((180, 240), Image.LANCZOS).save(os.path.join(ROOT, "covers/art", f"{b['slug']}.jpg"), quality=80)
        manifest[b["slug"]] = key
        json.dump(manifest, open(man_path, "w"), indent=0, sort_keys=True)
        print(f"[{i + 1}/{len(books)}] {b['slug']}")


def write(rel, text):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(text)


VERSION = datetime.now().strftime("%Y%m%d%H%M")

if __name__ == "__main__":
    books = load()
    print(len(books), "books")
    render_covers(books)
    books = [b for b in books if os.path.exists(os.path.join(ROOT, "covers", f"{b['slug']}.jpg"))]
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    for f in ("style.css", "app.js", "PaperMono.woff2", "PaperMono-OFL.txt"):
        shutil.copy(os.path.join(SRC, "static", f), os.path.join(ROOT, "assets", f))
    open(os.path.join(ROOT, "assets/favicon.svg"), "w").write(LOGO.replace('aria-hidden="true"', 'xmlns="http://www.w3.org/2000/svg"'))
    write("index.html", build_home(books))
    write("directory/index.html", build_directory(books))
    write("about/index.html", build_about(books))
    for i, b in enumerate(books):
        write(f"s1/{b['slug']}/index.html", build_article(b, books[i - 1] if i else None, books[i + 1] if i + 1 < len(books) else None))
    urls = ["/", "/directory/", "/about/"] + [f"/s1/{b['slug']}/" for b in books]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{SITE}{u}</loc></url>" for u in urls) + "</urlset>\n")
    print("built", len(books), "pages")
