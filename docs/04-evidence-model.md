# 04 — Evidence Model

The primary internal object is the **evidence unit**, not the document (proposal §8). Documents are
containers; evidence is what the answer is built from; claims are what the answer says.

```
Documents ──extract──► Evidence ──aggregate──► Claims ──synthesize──► Answer
```

## 1. Source tiers

Assigned at document creation from URL/publisher, refined after fetch from the document's own
metadata. Implemented in `primitives/sources.py`; shared by the search tools (`include_domains`),
the evidence quality score, the critic, and the evaluators.

| Tier | `source_quality` | Examples | Notes |
|---|---|---|---|
| `primary_policy` | 1.0 | `cms.gov/medicare-coverage-database` (NCD, LCD, Article), MAC sites (Noridian, CGS, Palmetto, NGS, WPS, Novitas, First Coast), `fda.gov` labels and approvals, `federalregister.gov`, `govinfo.gov`, `innovation.cms.gov` | The document that *is* the rule |
| `official_secondary` | 0.85 | CMS fact sheets, MLN Matters, CMS press releases, `medicare.gov` coverage pages, HHS/White House releases | Official but not the operative text; may lag or simplify |
| `professional` | 0.7 | ADA Standards of Care, AACE, Endocrine Society, AHRQ, KFF, health-system policy explainers | Authoritative on clinical practice, not on coverage |
| `trade` | 0.5 | Fierce Healthcare, STAT, Healthcare Dive, DME trade press, law-firm client alerts | Useful for change detection; must point to a primary source |
| `web` | 0.3 | vendor pages (Dexcom, Abbott coverage guides), blogs, forums, aggregators | Never sole support for a coverage claim |
| `unknown` | 0.3 | anything unclassified | Treated as `web` |

Rule used by the critic and the evaluators: a **coverage claim** (criteria, codes, exclusions,
effective dates) is `supported` only if at least one supporting evidence item is tier
`primary_policy` or `official_secondary`. Otherwise it is at best `weak`.

## 2. Document metadata extraction

After `fetch`, `primitives/docmeta.py` runs deterministic extractors over the text and title:

- `doc_type` and `document_id_external`: regexes for `LCD`, `L\d{5}`, `Article`, `A\d{5}`,
  `NCD \d+\.\d+`, `MLN\d+`, `Fact Sheet`, `Label`, `Press Release`.
- `effective_date` / `revision_date`: patterns like `Revision Effective Date`, `Effective Date`,
  `Original Effective Date`, `Revision Ending Date`, `Last Updated`, `Posted`, `Retirement Date`,
  `Issued` — with the nearest date token. CMS coverage-database pages state these explicitly.
- `publisher`: from domain and page header.
- Section headings: lines that match the CMS coverage-database section names (`Coverage Indications,
  Limitations, and/or Medical Necessity`, `Summary of Evidence`, `Coding Information`, `HCPCS
  Codes`, `Documentation Requirements`, `Revision History`) or Markdown/HTML heading markers.

Paragraphs are split on blank lines; each paragraph gets an index and char offsets used by
`Location`. Tables are kept as single paragraphs.

If extraction finds nothing, the fields stay `None` and the search agent is instructed to look for
the dates explicitly (rule 4 in 03 §4). Missing dates on policy documents are a critic finding.

## 3. Evidence creation rules

`add_evidence` enforces:

1. The document has been fetched (not `snippet_only`).
2. `evidence_text` is a verbatim substring of the referenced paragraph (whitespace-normalized
   comparison). If the agent paraphrased, the tool rejects it with the paragraph text so it can retry.
3. `claim_text` is one atomic statement, ≤ 200 chars.
4. `stance` ∈ supports / contradicts / context. `context` is for dates, definitions, scope notes.
5. `effective_date` defaults to the document's revision date if the passage has none.
6. `source_quality` is copied from the tier; `relevance` is set by the extractor model when
   `extract()` is used, or defaulted to 0.8 for agent-authored evidence.

`extract(doc_id, paragraph_indices, schema)` is the batch alternative: the extractor model reads
the selected paragraphs and returns a list of evidence candidates, each validated by the same rules.

## 4. Claim graph

`evidence/graph.py` maintains:

```
Claim ──supported_by──► Evidence
Claim ──contradicted_by──► Evidence
Claim ──derived_from──► Claim
Document ──supersedes──► Document      (same document_id_external, later revision_date)
```

Claim construction (`collect` node):

- Evidence items are grouped by `(branch_id, normalized claim_text)` using a simple embedding-free
  similarity (token Jaccard ≥ 0.6 on claim text) so near-duplicate claims from different agents
  merge. Good enough for the demo; an embedding step is a roadmap item.
- `status`:
  - `supported`: ≥ 1 supporting evidence at quality ≥ 0.85 and no contradicting evidence with
    confidence ≥ 0.6.
  - `contested`: supporting and contradicting evidence both present with confidence ≥ 0.6.
  - `weak`: supporting evidence only from tiers < 0.85, or a single supporting item with confidence
    < 0.6.
  - `unresolved`: no supporting evidence.
- `confidence`: `max(source_quality × confidence)` over supporting evidence, reduced by 0.3 if
  contested.
- `governing_date`: `effective_date` of the highest-quality supporting evidence.

Contradiction detection:

- Same branch, opposite stance, both confidence ≥ 0.6 → `contested`.
- Two evidence items, both `primary_policy`, same `document_id_external`, different
  `revision_date` → supersession edge; the earlier one's evidence is flagged `superseded` and
  excluded from `supported` status unless the later document lacks the passage.
- Two evidence items with different `effective_date` and the same claim text where the later one
  contradicts → flagged; the later date governs and the claim's text is annotated.

## 5. Citation format

In the answer body: `[n]`. In the sources list:

```
[3] LCD L33822 — Glucose Monitors, §Coverage Indications, Limitations, and/or Medical Necessity,
    revision effective 2023-04-16. Noridian (DME MAC). primary_policy.
    https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822
```

`Citation.label` is built by `evidence/cite.py` from document metadata; missing pieces are omitted,
never invented. The UI renders the evidence text on hover and links to the document view with the
paragraph highlighted.

## 6. Persistence

- Document text: `runs/<run_id>/docs/<doc_id>.txt` (plus `.meta.json`).
- Evidence, claims, graph edges: inside `state.json`.
- Tavily cache (optional): `.cache/tavily/<sha1(args)>.json` — used for bench reproducibility and
  GEPA cost control; never committed.

## 7. What the evaluators consume

- `Evidence[]` with `doc_id`, `evidence_text`, `effective_date` → evidence recall against the answer
  key's `required_evidence` (matched by document id/external id and key phrase).
- `Citation[]` + `Answer.body_markdown` → citation correctness (does the cited passage support the
  sentence?).
- `Claim.status` distribution and `Answer.contradictions` → contradiction handling.
- `Answer.effective_dates` and the governing document ids → currency.

See `05-evaluation-loop.md`.
