---
name: validate-bench
description: Interactive SearchBench answer-key validation for task 2.1. Presents one record at a time with live-source passages; applies the user's corrections; marks records validated. Invoke as /validate-bench (all) or /validate-bench cgm-elig-001
disable-model-invocation: true
---
Scope: $ARGUMENTS (empty = all records, highest-risk first per data/searchbench/README.md).

Precondition: `eval/searchbench/fetch_sources.py` has run and data/searchbench/sources/ exists. If not, run it first. Remind the user to `export ALLOW_BENCH_EDIT=1` in the shell running Claude Code; the write hook blocks the dataset otherwise.

For each record, present exactly this and then wait:
- Question, tier, split.
- Draft summary.
- For each required_claim: the claim text, then the best-matching passage(s) from the fetched sources (≤ 3 lines each, with document id and revision/effective date), or "NO SUPPORTING PASSAGE FOUND".
- For each required_evidence: found / not found, with the matched key phrases.
- Mismatches detected by fetch_sources (dates, codes).
- A one-line recommendation: "looks right", "date needs updating to X", "claim c2 unsupported — suggest rewriting as ...", or "convert to out_of_scope".

Then apply what the user says in plain English (edit only that record in searchbench_v0.jsonl; keep the JSON valid; do not touch other records). When the user says "validated", set `validated_by` to the name they gave (ask once), `as_of` to today's date, and move to the next record. Never mark a record validated on your own initiative. Never edit holdout-split records' `split` field.

At the end: print counts per split, run `uv run python -m eval.searchbench.sync`, and commit `eval: validate searchbench v0`.
