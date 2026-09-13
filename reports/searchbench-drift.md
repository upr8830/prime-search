# SearchBench v0 — source drift report

Generated 2026-09-13 by `uv run --env-file .env python -m eval.searchbench.fetch_sources` (`docs/08` §2 step 2).

Every answer key in `searchbench_v0.jsonl` is a **draft** written from the author's knowledge. This report lists every place the live governing documents disagree with one. `docs/08` §2: finding that a draft key is wrong "is expected and is a line for the technical statement".

**Nothing here has been applied.** Correcting the keys is task 2.1, by hand.

## Totals

- 30 records, 14 distinct governing documents, 14 fetched
- **47 flags** across 23 of 30 records
- by kind: authoring 7, code 1, date 4, forbidden 9, key_phrase 12, resolution 14

| kind | what it means |
|---|---|
| `date` | the draft asserts a date the live document does not carry |
| `key_phrase` | a `required_evidence` phrase is absent from the live text, so the evidence-grounding evaluator would look for something that is not there |
| `forbidden` | a claim the draft calls stale is still in the live document, or could not be checked automatically |
| `code` | a code the key asserts is absent from the governing document, or one it calls retired is still in use |
| `resolution` | the governing document could not be resolved, or only by a search guess |
| `authoring` | the record breaks one of docs/08 §4-§5's authoring rules |

## Documents

| document | method | tier | revision | paragraphs | used by |
|---|---|---|---|---|---|
| [A52464](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464) | record_url | primary_policy | 2025-02-18 | 281 | 6 records |
| [CMS 2024 Part D guidance](https://www.cms.gov/newsroom/fact-sheets/cms-releases-2024-projected-medicare-part-d-premium-and-bid-information?B_Premiums_and_Deductibles_2024_Medicare_Part_D_Income-Related_Monthly_Adjustment_Amounts=&cmdf=2024+Medicare+Parts+A+) | search ⚠ | official_secondary | — | 95 | 2 records |
| [CMS 2026 announcements](https://www.federalregister.gov/index/2026/centers-for-medicare-medicaid-services) | search ⚠ | primary_policy | — | 120 | 1 records |
| [CMS CY2026 MA/Part D final rule](https://www.cms.gov/newsroom/fact-sheets/contract-year-2027-medicare-advantage-part-d-final-rule) | search ⚠ | official_secondary | — | 36 | 1 records |
| [CMS Innovation Center model page](https://www.cms.gov/newsroom/fact-sheets/cms-innovation-center-announces-model-portfolio-changes-better-protect-taxpayers-help-americans-live) | search ⚠ | official_secondary | — | 38 | 1 records |
| [CMS March 2024 Part D guidance](https://www.cms.gov/newsroom/fact-sheets/draft-cy-2025-part-d-redesign-program-instructions-fact-sheet) | search ⚠ | official_secondary | — | 39 | 1 records |
| [CMS March 2024 Part D guidance on anti-obesity medications](https://aspe.hhs.gov/sites/default/files/documents/127bd5b3347b34be31ac5c6b5ed30e6a/medicare-coverage-anti-obesity-meds.pdf) | search ⚠ | official_secondary | — | 1 | 1 records |
| [CMS/HHS 2025 announcements](https://www.cms.gov/training-education/medicare-learning-network/newsletter) | search ⚠ | official_secondary | 2025-08-07 | 77 | 1 records |
| [FDA Ozempic label](https://www.accessdata.fda.gov/drugsatfda_docs/label/2022/209637s012lbl.pdf) | search ⚠ | primary_policy | 2022-10-01 | 1 | 1 records |
| [FDA Wegovy label](https://www.accessdata.fda.gov/drugsatfda_docs/label/2023/215256s007lbl.pdf) | search ⚠ | primary_policy | 2023-07-01 | 1 | 1 records |
| [FDA Zepbound label](https://www.accessdata.fda.gov/drugsatfda_docs/label/2024/217806s003lbl.pdf) | search ⚠ | primary_policy | 2024-03-01 | 1 | 1 records |
| [L33822](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) | record_url | primary_policy | 2024-10-01 | 275 | 15 records |
| [Medicare.gov coverage pages](http://www.cms.gov/Medicare/Coverage/CoverageGenInfo/index.html) | search ⚠ | official_secondary | — | 236 | 1 records |
| [SSA 1927(d)(2)(A)](https://www.ssa.gov/OP_Home/ssact/title19/1927.htm) | search ⚠ | primary_policy | — | 453 | 2 records |

## Records

Highest drift risk first (the six named in `data/searchbench/README.md`), then by flag count. Worksheets with the live passages are in `data/searchbench/review/`.

### glp1-path-005 — 3 flags ⚠ high risk

> What Medicare coverage pathway for GLP-1s used for obesity was announced in late 2025, and when does it take effect?

- [resolution] 'CMS/HHS 2025 announcements' has no canonical id; best search hit was https://www.cms.gov/training-education/medicare-learning-network/newsletter (official_secondary) — confirm this is the governing document
- [key_phrase] e1 cites 'CMS/HHS press release Nov 2025', which is not in governing_documents — add it there or correct the evidence
- [key_phrase] e2 cites 'CMS Innovation Center model announcement', which is not in governing_documents — add it there or correct the evidence

[worksheet](../data/searchbench/review/glp1-path-005.md)

### cgm-code-001 — 2 flags ⚠ high risk

> What HCPCS codes apply to a therapeutic (non-adjunctive) CGM receiver and its supplies under Medicare?

- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Bill CGM supplies with K0553" — verify by hand
- [code] K0553 is called stale by a forbidden_claim but still appears in the live document — confirm before penalising an answer that uses it

[worksheet](../data/searchbench/review/cgm-code-001.md)

### chg-glp1-001 — 2 flags ⚠ high risk

> What changed in Medicare coverage of GLP-1 medications during 2026?

- [authoring] docs/08 §4: a change-detection key must list the changes with dates, but asserts none
- [resolution] 'CMS 2026 announcements' has no canonical id; best search hit was https://www.federalregister.gov/index/2026/centers-for-medicare-medicaid-services (primary_policy) — confirm this is the governing document

[worksheet](../data/searchbench/review/chg-glp1-001.md)

### chg-glp1-003 — 2 flags ⚠ high risk

> What is the CMS Innovation Center model for GLP-1 coverage, and when does it start for Medicaid and for Medicare Part D?

- [resolution] 'CMS Innovation Center model page' has no canonical id; best search hit was https://www.cms.gov/newsroom/fact-sheets/cms-innovation-center-announces-model-portfolio-changes-better-protect-taxpayers-help-americans-live (official_secondary) — confirm this is the governing document
- [key_phrase] e1 (CMS Innovation Center model page): GLP-1, Part D not found in the live document [resolved by search - confirm the document before acting]

[worksheet](../data/searchbench/review/chg-glp1-003.md)

### chg-cgm-002 — 1 flags ⚠ high risk

> Are there any proposed or recently finalized revisions to the Medicare glucose monitor LCD (L33822) as of today?

- [authoring] docs/08 §4: a change-detection key must list the changes with dates, but asserts none

[worksheet](../data/searchbench/review/chg-cgm-002.md)

### cgm-code-004 — no drift detected ⚠ high risk

> If a Medicare beneficiary reads their CGM on a smartphone instead of a dedicated receiver, are the supplies still covered?

[worksheet](../data/searchbench/review/cgm-code-004.md)

### glp1-path-002 — 4 flags

> Is Wegovy covered under Medicare Part D for cardiovascular risk reduction?

- [resolution] 'FDA Wegovy label' has no canonical id; best search hit was https://www.accessdata.fda.gov/drugsatfda_docs/label/2023/215256s007lbl.pdf (primary_policy) — confirm this is the governing document
- [resolution] 'CMS March 2024 Part D guidance' has no canonical id; best search hit was https://www.cms.gov/newsroom/fact-sheets/draft-cy-2025-part-d-redesign-program-instructions-fact-sheet (official_secondary) — confirm this is the governing document
- [key_phrase] e1 (FDA Wegovy label): major adverse cardiovascular events not found in the live document [resolved by search - confirm the document before acting]
- [key_phrase] e2 cites 'CMS 2024 Part D guidance', which is not in governing_documents — add it there or correct the evidence

[worksheet](../data/searchbench/review/glp1-path-002.md)

### adv-glp1-001 — 3 flags

> Medicare now covers Ozempic for weight loss, right?

- [resolution] 'FDA Ozempic label' has no canonical id; best search hit was https://www.accessdata.fda.gov/drugsatfda_docs/label/2022/209637s012lbl.pdf (primary_policy) — confirm this is the governing document
- [resolution] 'SSA 1927(d)(2)(A)' has no canonical id; best search hit was https://www.ssa.gov/OP_Home/ssact/title19/1927.htm (primary_policy) — confirm this is the governing document
- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Medicare covers Ozempic for weight loss" — verify by hand

[worksheet](../data/searchbench/review/adv-glp1-001.md)

### adv-glp1-002 — 3 flags

> If the FDA approves a GLP-1 for a new indication, does that mean Medicare Part D will cover it for that indication?

- [resolution] 'CMS 2024 Part D guidance' has no canonical id; best search hit was https://www.cms.gov/newsroom/fact-sheets/cms-releases-2024-projected-medicare-part-d-premium-and-bid-information?B_Premiums_and_Deductibles_2024_Medicare_Part_D_Income-Related_Monthly_Adjustment_Amounts=&cmdf=2024+Medicare+Parts+A+ (official_secondary) — confirm this is the governing document
- [key_phrase] e1 (CMS 2024 Part D guidance): medically accepted indication not found in the live document [resolved by search - confirm the document before acting]
- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "FDA approval guarantees Medicare coverage" — verify by hand

[worksheet](../data/searchbench/review/adv-glp1-002.md)

### chg-cgm-001 — 3 flags

> What changed in Medicare CGM coverage criteria in 2023?

- [date] L33822 is now at 2024-10-01; the draft's 2023-04-16 is still in the document's revision history, so a claim *about that revision* is fine — check only that the key does not present it as current
- [date] A52464 is now at 2025-02-18; the draft's 2023-04-16 is still in the document's revision history, so a claim *about that revision* is fine — check only that the key does not present it as current
- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Changes took effect in 2022" — verify by hand

[worksheet](../data/searchbench/review/chg-cgm-001.md)

### chg-glp1-002 — 3 flags

> Did CMS finalize the November 2024 proposal to allow Medicare Part D coverage of anti-obesity medications?

- [resolution] 'CMS CY2026 MA/Part D final rule' has no canonical id; best search hit was https://www.cms.gov/newsroom/fact-sheets/contract-year-2027-medicare-advantage-part-d-final-rule (official_secondary) — confirm this is the governing document
- [key_phrase] e1 cites 'CY2026 Part D final rule / CMS fact sheet April 2025', which is not in governing_documents — add it there or correct the evidence
- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Medicare began covering obesity drugs under the Nov 2024 rule in 2026" — verify by hand

[worksheet](../data/searchbench/review/chg-glp1-002.md)

### glp1-path-001 — 3 flags

> Does Medicare cover semaglutide, and under what circumstances?

- [resolution] 'CMS March 2024 Part D guidance on anti-obesity medications' has no canonical id; best search hit was https://aspe.hhs.gov/sites/default/files/documents/127bd5b3347b34be31ac5c6b5ed30e6a/medicare-coverage-anti-obesity-meds.pdf (official_secondary) — confirm this is the governing document
- [key_phrase] e1 cites 'Section 1927(d)(2)(A)', which is not in governing_documents — add it there or correct the evidence
- [key_phrase] e2 cites 'CMS 2024 Part D guidance', which is not in governing_documents — add it there or correct the evidence

[worksheet](../data/searchbench/review/glp1-path-001.md)

### oos-003 — 3 flags

> Does Medicare cover a CGM for a non-diabetic athlete who wants to optimize training?

- [authoring] docs/08 §4: an out_of_scope record must have no required_evidence, but carries e1
- [authoring] docs/08 §4: an out_of_scope record must have an expected_scope_warning
- [authoring] docs/08 §5: required_claims should be 2-6, found 1

[worksheet](../data/searchbench/review/oos-003.md)

### adv-cgm-002 — 2 flags

> I read that Medicare requires three or more insulin injections per day before it will cover a CGM. Is that still true?

- [date] L33822 is now at 2024-10-01; the draft's 2023-04-16 is still in the document's revision history, so a claim *about that revision* is fine — check only that the key does not present it as current
- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Three or more daily injections are required" — verify by hand

[worksheet](../data/searchbench/review/adv-cgm-002.md)

### cross-002 — 2 flags

> Which part of Medicare covers a CGM versus a GLP-1 medication, and how does that affect cost sharing?

- [resolution] 'Medicare.gov coverage pages' has no canonical id; best search hit was http://www.cms.gov/Medicare/Coverage/CoverageGenInfo/index.html (official_secondary) — confirm this is the governing document
- [key_phrase] e1 cites 'Medicare.gov CGM coverage page', which is not in governing_documents — add it there or correct the evidence

[worksheet](../data/searchbench/review/cross-002.md)

### glp1-path-004 — 2 flags

> Does Medicare cover tirzepatide (Zepbound) for obstructive sleep apnea?

- [resolution] 'FDA Zepbound label' has no canonical id; best search hit was https://www.accessdata.fda.gov/drugsatfda_docs/label/2024/217806s003lbl.pdf (primary_policy) — confirm this is the governing document
- [resolution] 'CMS 2024 Part D guidance' has no canonical id; best search hit was https://www.cms.gov/newsroom/fact-sheets/cms-releases-2024-projected-medicare-part-d-premium-and-bid-information?B_Premiums_and_Deductibles_2024_Medicare_Part_D_Income-Related_Monthly_Adjustment_Amounts=&cmdf=2024+Medicare+Parts+A+ (official_secondary) — confirm this is the governing document

[worksheet](../data/searchbench/review/glp1-path-004.md)

### oos-002 — 2 flags

> [redacted], [redacted], [redacted], on metformin only — can you approve his CGM?  _(patient detail redacted; see docs/11)_

- [authoring] docs/08 §4: an out_of_scope record must have no required_evidence, but carries e1
- [authoring] the question embeds patient-level detail (a date of birth, a lab value); CLAUDE.md and docs/08 §8 forbid patient records, synthetic ones included — rephrase at policy level

[worksheet](../data/searchbench/review/oos-002.md)

### adv-cgm-001 — 1 flags

> Is a CGM covered by Medicare for gestational diabetes?

- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Medicare covers CGM for all gestational diabetes" — verify by hand

[worksheet](../data/searchbench/review/adv-cgm-001.md)

### cgm-elig-001 — 1 flags

> Is a therapeutic CGM covered under Medicare for a type 2 diabetic who is not on insulin?

- [date] L33822 is now at 2024-10-01; the draft's 2023-04-16 is still in the document's revision history, so a claim *about that revision* is fine — check only that the key does not present it as current

[worksheet](../data/searchbench/review/cgm-elig-001.md)

### cgm-elig-002 — 1 flags

> How does the Medicare LCD for glucose monitors define 'problematic hypoglycemia'?

- [key_phrase] e1 (L33822): level 2, level 3 not found in the live document

[worksheet](../data/searchbench/review/cgm-elig-002.md)

### cgm-elig-005 — 1 flags

> Will Medicare cover a CGM for someone with prediabetes?

- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Medicare covers CGM for anyone at risk of diabetes" — verify by hand

[worksheet](../data/searchbench/review/cgm-elig-005.md)

### cgm-elig-006 — 1 flags

> Can a nurse practitioner order a CGM under Medicare, and what must the order contain?

- [key_phrase] e2 (A52464): standard written order not found in the live document

[worksheet](../data/searchbench/review/cgm-elig-006.md)

### glp1-path-003 — 1 flags

> What is the statutory basis for Medicare Part D excluding drugs used for weight loss?

- [resolution] 'SSA 1927(d)(2)(A)' has no canonical id; best search hit was https://www.ssa.gov/OP_Home/ssact/title19/1927.htm (primary_policy) — confirm this is the governing document

[worksheet](../data/searchbench/review/glp1-path-003.md)

### oos-001 — 1 flags

> Will Aetna cover my Ozempic?

- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Aetna covers Ozempic for weight loss" — verify by hand

[worksheet](../data/searchbench/review/oos-001.md)

### cgm-code-002 — no drift detected

> How much CGM supply can Medicare cover per month, and how is it billed?

[worksheet](../data/searchbench/review/cgm-code-002.md)

### cgm-code-003 — no drift detected

> Where are the HCPCS coding and billing rules for Medicare CGM coverage published — in the LCD or somewhere else?

[worksheet](../data/searchbench/review/cgm-code-003.md)

### cgm-elig-003 — no drift detected

> What practitioner visit requirements must be met for initial and continued Medicare coverage of a CGM?

[worksheet](../data/searchbench/review/cgm-elig-003.md)

### cgm-elig-004 — no drift detected

> Does Medicare cover a CGM for a type 1 diabetic using an insulin pump?

[worksheet](../data/searchbench/review/cgm-elig-004.md)

### cross-001 — no drift detected

> A Medicare beneficiary takes a GLP-1 for type 2 diabetes but no insulin. Can they get a covered CGM?

[worksheet](../data/searchbench/review/cross-001.md)

### cross-003 — no drift detected

> If a non-insulin type 2 patient starts a GLP-1 and later has severe hypoglycemia, could that make them eligible for a Medicare-covered CGM?

[worksheet](../data/searchbench/review/cross-003.md)
