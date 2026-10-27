# Backfill task: write books for new filings

You write books for S1 Directory (s1directory.com), a library of tech S-1 filings bound as books.

1. Read `site-src/WRITER_BRIEF.md` for the entry fields and the cover rules.
2. Read `site-src/COPY_BRIEF.md` for how to write. It overrides the writing rules in the first brief.
3. Your input is a JSON array of filings (path given in your task). Write one entry per filing, same order,
   to the output path given in your task.

## Research

These are recent IPOs (2018 to 2026), so do not write from memory alone. For each company, use web search
to confirm: what it does, founders, founding year, HQ, IPO date and price, how the first day went, and
where the company is today (still public, acquired, taken private). Write `fate` as of October 2026.
The input `price` may be null or wrong: put the confirmed IPO price per share in a `"price"` key in your entry
(a number). For a direct listing, use the NYSE/Nasdaq reference price and say "direct listing" in the essay.
If the input `ticker` is null or wrong, add a `"ticker"` key with the right one.

If a company turns out to be a shell, a SPAC, a tiny microcap with no real business, or not a tech company,
do not write an entry. Instead add it to a `"skip"` list at the end of your report with a one-line reason.

## Covers

- Do not reuse art. The ids already used are in `site-src/used-art.txt` (one image_id per line).
  Also do not reuse an image_id within your own batch.
- Check every image downloads before you use it:
  `curl -s -o /dev/null -w "%{http_code}" "https://www.artic.edu/iiif/2/<image_id>/full/843,/0/default.jpg"` must print 200.

## Output

A JSON array written with the Write tool. Validate it with
`python3 -c "import json;d=json.load(open(PATH));print(len(d))"`.
Reply with: the count written, the skip list with reasons, and any fact you could not confirm.

## Rows with `"source": "manual"`

These came from a list of famous IPOs, not from EDGAR, so the filing data is empty. Find it on EDGAR and add a
`"filing"` object to the entry:

```json
"filing": {"name": "Legal name as on EDGAR", "date": "YYYYMMDD (the day the IPO priced)", "sic": "4-digit SIC from EDGAR",
           "ticker": "TICK", "price": 85.0, "s1": "https://www.sec.gov/Archives/edgar/data/<cik>/<accession-no-dashes>/<accession>-index.htm"}
```

`s1` must link to the index page of the company's original S-1 (or F-1 for a foreign company), not an amendment.
Find it with the company's EDGAR filing list: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<cik>&type=S-1&dateb=&owner=include&count=40`
(use `type=F-1` for foreign filers). Check the link returns 200.

## SEC requests

Send every request to sec.gov with the header `User-Agent: S1Directory research bot https://www.s1directory.com`.
Never put a personal email address in a request.
