# Weekly routine: add new IPOs to S1 Directory

A scheduled Claude Code routine follows these steps. The goal is one pull request a week with the
new books, ready for Sharan to review. Never push to `master`: a push to `master` deploys the live site.

## 1. Set up

```
python3 -m venv .venv && .venv/bin/pip install -q -r site-src/requirements.txt
git checkout -b ipos/$(date +%Y-%m-%d)
```

## 2. Discover new IPOs

```
.venv/bin/python site-src/tools/discover.py --write
```

This finds 424B4 prospectuses on EDGAR since the newest filing in `filings.json`, keeps first-time
tech IPOs, and appends them to `filings.json`. Then list the queue (oldest first, at most 20 a run):

```
.venv/bin/python site-src/tools/pending.py --limit 20
```

If the queue is empty, stop. Do not open a pull request.

## 3. Decide what belongs

The directory is for real tech and internet companies a reader would care about. For each pending filing:

- **Keep** venture-backed or well-known tech companies, and any company with real press coverage of its IPO.
- **Skip** shell companies, SPACs, tiny microcaps (roughly under $40M raised), Chinese/HK holding-company
  microcaps, crypto-mining shells, and companies that are not tech.

For each skip: remove it from `filings.json` and add it to `site-src/skipped.json` as
`"<cik>": "<name>: <short reason>"` (the CIK is in the `s1` URL, `/edgar/data/<cik>/`).
This stops discovery from finding it again.

For each keep: check the data with a web search. Fix the `name`, `ticker`, and `price`
(the IPO price per share) in `filings.json` if they are wrong or null.

## 4. Write the entries

Read `site-src/WRITER_BRIEF.md` and follow it exactly. Write all new entries for this run to a new
file, `site-src/entries-YYYY-MM-DD.json` (today's date).

- Recent IPOs need web research: what the company does, founders, founding year, HQ, IPO price,
  and how the stock did. Write `fate` as of today, e.g. "Still public (NYSE: XYZ)".
- Cover art must not repeat. Get the used ids with `.venv/bin/python site-src/tools/pending.py --art`
  and pick only image_ids that are not in that list.
- Check each cover image downloads: `curl -s -o /dev/null -w "%{http_code}" "https://www.artic.edu/iiif/2/<image_id>/full/843,/0/default.jpg"` must print 200.

## 5. Build and check

```
.venv/bin/python site-src/build.py
```

The output must say `built N pages` with N equal to the old count plus the new entries. Fix any errors.
Open two or three of the new `s1/<slug>/index.html` pages and check that the essay and cover are present.

## 6. Open the pull request

Commit everything (the new entries, `filings.json`, `skipped.json`, and the generated site files),
push the branch, and open a pull request against `master`:

- Title: `Add N new IPOs (<first name>, <second name>, …)`
- Body: a table of the new books (name, ticker, IPO date, price, cover artwork), then the skipped
  companies with reasons, then any fact you could not confirm.

Do not merge it. Sharan reviews and merges.
