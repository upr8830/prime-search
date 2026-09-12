# SearchBench v0 (seed)

30 questions on Medicare coverage of CGM and GLP-1 medications. Schema and construction rules:
`docs/08-synthetic-data-spec.md`. Evaluators that consume this file: `docs/05-evaluation-loop.md`.

**Every record is a DRAFT.** `answer_key.validated_by` is `null` and `as_of` is `null`. The keys were
written from the author's knowledge (cutoff mid-2026) and are expected to contain stale dates, codes,
or claims. Before any evaluation run:

1. `uv run python -m eval.searchbench.fetch_sources` — pulls the current governing documents via
   Tavily into `sources/` and prints, per record, the passages matching each `required_evidence`
   key phrase and any date/code mismatches versus the draft.
2. Review each record against those passages; correct `summary`, `required_claims`,
   `required_evidence`, `forbidden_claims`, `governing_documents`, `sources`; set `as_of` and
   `validated_by`; add `validation_notes`.
3. `uv run python -m eval.searchbench.sync` — pushes to LangSmith as `searchbench-v0` with splits.

Records with the highest drift risk (validate first): `glp1-path-005`, `chg-glp1-001`, `chg-glp1-003`,
`chg-cgm-002`, `cgm-code-004`, `cgm-code-001`.

Splits: train 15 · dev 5 · holdout 10. Never run GEPA on holdout.

Fields per record: `id`, `domain` (cgm | glp1 | cross | other), `tier` (1–4), `question_type`,
`question`, `split`, `answer_key{as_of, summary, required_claims[], required_evidence[],
governing_documents[], expected_contradictions[], expected_scope_warning, forbidden_claims[],
sources[], validated_by, validation_notes}`.
