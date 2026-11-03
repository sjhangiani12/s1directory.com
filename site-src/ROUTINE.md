# Weekly routine: add new IPOs to S1 Directory

A scheduled Claude Code routine follows these steps every week. It publishes the new books itself:
a push to `master` deploys the live site. It falls back to a pull request only when something needs a
human (see step 7). Never force-push, and never rewrite history on `master`.

## 1. Set up

```
python3 -m venv .venv && .venv/bin/pip install -q -r site-src/requirements.txt
git checkout -b ipos/$(date +%Y-%m-%d)
```

## 2. Discover new IPOs

```
.venv/bin/python site-src/tools/discover.py --write
```

This finds 424B4 prospectuses (priced IPOs) and first-time S-1 / F-1 filings (on file, not priced yet)
on EDGAR, keeps tech companies, and appends them to `filings.json`. A filed-but-unpriced company gets
`price: null` and its S-1 date; the site shows it as "S-1 filed · not yet priced". When an unpriced
company later prices, discovery updates its date, price and ticker in place. If that happens, update
the `fate` and any "not yet priced" wording in its entry too. Then list the queue (oldest first, at most 20 a run):

```
.venv/bin/python site-src/tools/pending.py --limit 20
```

If the queue is empty, stop. Do not open a pull request.

## 3. Decide what belongs

The directory is for real tech and internet companies a reader would care about. For each pending filing:

- **Keep** venture-backed or well-known tech companies, and any company with real press coverage of its IPO.
- An S-1 filer belongs only if it is a company people will search for (real press coverage, known
  investors, or a large raise). Most S-1 filers are tiny shells: skip them.
- **Skip** shell companies, SPACs, ETFs and trusts, tiny microcaps (roughly under $40M raised), Chinese/HK holding-company
  microcaps, crypto-mining shells, and companies that are not tech.

For each skip: remove it from `filings.json` and add it to `site-src/skipped.json` as
`"<cik>": "<name>: <short reason>"` (the CIK is in the `s1` URL, `/edgar/data/<cik>/`).
This stops discovery from finding it again.

For each keep: check the data with a web search. Fix the `name`, `ticker`, and `price`
(the IPO price per share) in `filings.json` if they are wrong or null.

## 4. Write the entries

Read `site-src/WRITER_BRIEF.md` (fields and cover rules) and `site-src/COPY_BRIEF.md` (how to write; it overrides the writing rules in the first brief). Follow both exactly. Write all new entries for this run to a new
file, `site-src/entries-YYYY-MM-DD.json` (today's date).

- Recent IPOs need web research: what the company does, founders, founding year, HQ, IPO price,
  and how the stock did. Write `fate` as of today, e.g. "Still public (NYSE: XYZ)".
- Cover art must not repeat. Get the used ids with `.venv/bin/python site-src/tools/pending.py --art`
  and pick only image_ids that are not in that list.
- Check each cover image downloads: `curl -s -o /dev/null -w "%{http_code}" "https://www.artic.edu/iiif/2/<image_id>/full/843,/0/default.jpg"` must print 200.

## 5. Build the S-1 readers

```
.venv/bin/python site-src/tools/readers.py
.venv/bin/python site-src/tools/qa_readers.py <new slugs>
```

This converts each new S-1 into `s1/<slug>/s1.json.gz` for the on-site reader. A conversion failure
is fine (the page links to EDGAR); list it in the PR body. Do not make PDFs: Sharan prints and uploads
those from a laptop with `tools/pdfs.py --upload`, because R2 needs a Cloudflare login.

## 6. Build and check

```
.venv/bin/python site-src/build.py
```

The output must say `built N pages` with N equal to the old count plus the new entries. Fix any errors.
Open two or three of the new `s1/<slug>/index.html` pages and check that the essay and cover are present.

## 7. Publish, or ask for review

Commit everything (the new entries, `filings.json`, `skipped.json`, and the generated site files)
with the message `Add N new IPOs (<first name>, <second name>, …)`. The body lists the new books
(name, ticker, IPO date, price) and the skipped companies with reasons.

**Publish** (merge the branch into `master` and push `master`) only when all of these are true:

- `build.py` finished without errors, and the page count went up by exactly the number of new entries.
- Every new book has a cover image that downloaded, and an essay with every field from the brief.
- You confirmed each kept company's IPO date and price (or "S-1 filed, not priced") from EDGAR or
  a reliable news source. You found no conflicting facts.
- No existing book's entry changed, except a price update for a filing that priced.

Before the push, run `git pull --rebase origin master` and build again if anything came in.

**Open a pull request instead** (push the branch, PR against `master`, do not merge) when any check
fails or you are unsure about a fact. Put the reason at the top of the PR body.

If the only changes are new skips in `skipped.json`, publish them with the message
`Skip N EDGAR filers (no new IPOs this week)`. If nothing changed at all, stop.

After a push to `master`, `.github/workflows/indexnow.yml` sends the new pages to IndexNow.
New books have no PDF until someone runs `tools/pdfs.py --upload` on a laptop. The reader works without it.
