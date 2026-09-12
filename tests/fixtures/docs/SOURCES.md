# docmeta fixtures (docs/09 §1.3)

Raw `raw_content` from Tavily Extract (advanced depth, markdown), run through
`normalize_text` once so the bytes on disk are exactly what `fetch` would persist.
Frozen inputs, which is what lets `tests/test_docmeta.py` assert exact dates and
section names; drift against the live pages is caught separately by
`tests/test_primitives_live.py -m live`.

`data/searchbench/sources/` (docs/08 §2) is a different thing and arrives at task
1.8 — it serves the benchmark, not these unit tests.

All three are public-domain U.S. government content.

| file | url | retrieved | sha1 | chars | paragraphs |
|---|---|---|---|---|---|
| `cms-lcd-l33822.raw.md` | <https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822> | 2026-09-12 | `d3d101467580` | 78,946 | 275 |
| `cms-article-a52464.raw.md` | <https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464> | 2026-09-12 | `9c8e4c432dc6` | 146,976 | 281 |
| `fda-label-ozempic.raw.md` | <https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=adec4fd2-6858-4c99-91d4-531f5f2a2d79> | 2026-09-12 | `e7e8591b8d78` | 176,585 | 633 |

## Why these three

docs/09 §1.3 asks for "two saved CMS pages (LCD + article) and one FDA label page".

The FDA label is the **DailyMed SPL**, not the Drugs@FDA PDF: Tavily Extract cannot
read `accessdata.fda.gov/drugsatfda_docs/label/...pdf` (it raises rather than
returning results, measured 2026-09-12), while DailyMed serves the same FDA-approved
label text as HTML. Ozempic rather than a device clearance because GLP-1 is half of
SearchBench, and a drug label is what those questions actually cite.

## What they demonstrate

* **L33822** — the CMS header metadata block is JavaScript-rendered and absent from
  the extract, so the revision date exists only in the Revision History table, and
  there is no Original Effective Date at all. Also holds the "Associated Documents"
  table whose *column header* says `Effective Dates`, the trap that made an early
  version read another column's value as the effective date.
* **A52464** — same missing header block, plus a 52 KB ICD-10 table that must stay a
  single paragraph (docs/04 §2) and therefore forced BM25 windowing.
* **Ozempic** — dates itself "Revised: 5/2026" / "Updated June 1, 2026", neither of
  which is a label docs/04 §2 lists nor a full date.

## Refresh

Needs `TAVILY_API_KEY`. Review the diff before committing: a changed revision date is
a real-world finding worth a decision-log line, not noise (docs/08 §2).

```bash
uv run --env-file .env python tests/fixtures/docs/refresh.py
```
