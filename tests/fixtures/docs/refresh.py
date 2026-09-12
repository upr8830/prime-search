"""Refresh the docmeta fixtures from the live pages.

    uv run python tests/fixtures/docs/refresh.py

The fixtures are frozen inputs, so tests/test_docmeta.py can assert exact dates and
section names; drift against the live pages is caught separately by
tests/test_primitives_live.py. Review the diff before committing a refresh — a
changed revision date is a real-world finding, not noise (docs/08 §2).

This script is the only writer, so the bytes stay reproducible.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from prime_search.primitives import extract_tool, normalize_text, split_paragraphs  # noqa: E402

HERE = Path(__file__).parent

# docs/09 §1.3: "two saved CMS pages (LCD + article) and one FDA label page".
# The FDA label is the DailyMed SPL rather than the Drugs@FDA PDF: Tavily Extract
# cannot read that PDF (it raises rather than returning results, measured
# 2026-09-12), and DailyMed carries the same FDA-approved label text as HTML.
FIXTURES: dict[str, str] = {
    "cms-lcd-l33822": "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822",
    "cms-article-a52464": (
        "https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464"
    ),
    "fda-label-ozempic": (
        "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm"
        "?setid=adec4fd2-6858-4c99-91d4-531f5f2a2d79"
    ),
}


def main() -> int:
    rows = []
    for slug, url in FIXTURES.items():
        response = extract_tool().invoke({"urls": [url]})
        if not isinstance(response, dict) or not response.get("results"):
            print(f"FAIL {slug}: {str(response)[:200]}")
            return 1
        result = response["results"][0]
        text = normalize_text(result.get("raw_content") or "")
        path = HERE / f"{slug}.raw.md"
        path.write_text(text, encoding="utf-8", newline="\n")
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        rows.append((path.name, url, digest, len(text), len(split_paragraphs(text))))
        print(
            f"{path.name:28} {len(text):7,} chars  "
            f"{len(split_paragraphs(text)):4} paragraphs  {digest[:12]}  "
            f"title={result.get('title')!r}"
        )

    table = "\n".join(
        f"| `{name}` | <{url}> | {date.today().isoformat()} | `{digest[:12]}` | {chars:,} | {paras} |"
        for name, url, digest, chars, paras in rows
    )
    print("\nPaste into SOURCES.md:\n")
    print("| file | url | retrieved | sha1 | chars | paragraphs |")
    print("|---|---|---|---|---|---|")
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
