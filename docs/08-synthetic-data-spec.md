# 08 — Synthetic Data Specification (SearchBench v0)

"Synthetic" here means the *questions* are authored, not scraped, and the *answer keys* are
constructed from live primary sources and validated by a human. No patient data; no synthetic
patients. Questions are about policy.

## 1. Why answer keys cannot come from prior knowledge

Coverage policy changed materially in 2023 (CGM criteria) and 2024–2026 (GLP-1). The author's
knowledge is a snapshot; the assignment is evaluated in September 2026. Every answer key therefore
records `as_of`, the source URLs it was built from, and who validated it. Keys are treated as
data with provenance, not as facts the author remembers.

## 2. Construction process (Day 1, ~2 hours)

1. **Seed questions** — `data/searchbench/searchbench_v0.jsonl` ships with 30 questions and
   *draft* answer keys marked `"validated_by": null`. The draft keys encode what the author expects
   as of mid-2026 and, for each, which primary document should govern.
2. **Fetch governing documents** — `uv run python -m eval.searchbench.fetch_sources` uses the
   primitives (Tavily search restricted to `cms.gov`, MAC domains, `fda.gov`; Tavily extract) to pull
   the current text of every document in `governing_documents`, store it under
   `data/searchbench/sources/<doc>.txt` with retrieval date and revision date, and print a diff
   summary against the draft key's expectations (e.g., "L33822 revision date found: 2025-xx-xx —
   draft expected 2023-04-16").
3. **Human validation** — the author opens each record, reads the fetched source passages that
   `fetch_sources` highlighted for each `required_claim` and `required_evidence`, corrects the key,
   sets `as_of`, `validated_by`, and notes. Budget: ~3 minutes per question.
4. **Freeze** — `uv run python -m eval.searchbench.sync` pushes to LangSmith as `searchbench-v0`
   with splits. The file is committed; the sources folder is committed too (small text files with
   public-domain government content) so the report is reproducible.

If a draft key turns out to be wrong, that is expected and is a line for the technical statement:
the pipeline caught policy drift the author did not know about.

## 3. Question taxonomy

| Type | Count | Tier | What it tests |
|---|---|---|---|
| eligibility (CGM) | 6 | 1–3 | criteria, non-insulin pathway, hypoglycemia definition, visit requirements |
| coding & supply (CGM) | 4 | 2 | article vs LCD, codes, frequency limits, supplier docs |
| coverage pathway (GLP-1) | 5 | 2–3 | Part D vs statutory exclusion, CV indication, obesity pathway timing |
| change detection (both) | 5 | 3 | ordered changes with dates; currency |
| contradiction / adversarial | 4 | 4 | secondary sources overstating coverage; superseded criteria; label vs coverage |
| cross-benefit | 3 | 3 | Part B (CGM) vs Part D (GLP-1); combined questions |
| out of scope | 3 | 4 | commercial payers; individual patient; non-diabetes use |

Total 30. Tier definition: 1 = one primary document answers it; 2 = two documents or one document
plus date reasoning; 3 = multiple documents, supersession, or time-ordered changes; 4 = designed to
mislead a single-search agent.

## 4. Authoring rules for questions

- Phrase as a practitioner would, including the ambiguity a practitioner would leave ("not on
  insulin", "for weight loss", "this year").
- Each question has exactly one governing set of documents as of `as_of`.
- Adversarial questions must have a plausible wrong answer that a top-ranked secondary page would
  give. Record that wrong answer in `forbidden_claims` with a reason.
- Change-detection questions must be answerable with an ordered list; the key lists the changes
  with dates and the document that establishes each.
- Out-of-scope questions must have an `expected_scope_warning` and no `required_evidence`.

## 5. Answer key authoring rules

- `required_claims`: 2–6 atomic statements; mark `must` for the ones without which the answer is
  wrong. Write them so an LLM judge can check presence, not style.
- `required_evidence`: the document(s) and 1–3 key phrases that must appear in cited evidence text.
  Use the external id (`L33822`, `A52464`, `NCD ...`) when the document has one.
- `forbidden_claims`: statements that are stale or false; each with `reason`.
- `governing_documents`: external ids or canonical URLs.
- `expected_contradictions`: plain-language descriptions ("secondary sources state CGM is covered
  for all diabetics; the LCD requires insulin or problematic hypoglycemia").
- `summary`: 2–4 sentences a reviewer would accept as correct.

## 6. Splits

Assigned by a fixed seed with stratification on `tier` and `domain`:
`train` 15, `dev` 5, `holdout` 10. Out-of-scope and adversarial records are spread so each split has
at least one. The split is a field in the record; changing it is a versioned dataset change.

## 7. Versioning

`searchbench_v0` is the frozen set for this delivery. Candidates from UI feedback go to
`candidates.jsonl` and, if validated, into `searchbench_v1` after the report is produced — never
into v0.

## 8. Not included, deliberately

- Questions requiring MAC-specific variation across jurisdictions (all DME MACs share the CGM
  LCD content, which keeps the demo tractable).
- Commercial payer policies (roadmap).
- Non-English sources.
- Any patient-level inputs.

## 9. Seed file

`data/searchbench/searchbench_v0.jsonl` is delivered alongside this spec with 30 records whose keys
are drafts (`validated_by: null`). The `README.md` in that folder repeats the validation procedure.
