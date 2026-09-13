# adv-cgm-002 — validation worksheet

**I read that Medicare requires three or more insulin injections per day before it will cover a CGM. Is that still true?**

`cgm` · tier 4 · contradiction · split `holdout`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [date] L33822 is now at 2024-10-01; the draft's 2023-04-16 is still in the document's revision history, so a claim *about that revision* is fine — check only that the key does not present it as current
- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Three or more daily injections are required" — verify by hand

## Draft summary

No. That requirement existed before April 16, 2023 and was removed by the LCD revision; any source stating it is out of date. Current criteria: insulin treatment (any regimen) or problematic hypoglycemia.

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

The multiple-daily-injection requirement was removed effective April 16, 2023

> Revision Effective Date: 02/28/2022
CMS NATIONAL COVERAGE POLICY:
Removed: "CMS Ruling 1682R"
COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY:
Removed: Reference to CMS Ruling 1682R
Added: CGM refers to both therapeutic/nonadjunctive and non-therapeutic/adjunctive CGMs
Added: Language describing "therapeutic," "non-adjunctive," "non-therapeutic," and "adjunctive" terms and term usage
Added: Information regarding classification of CGMs as DME
Revised: Coverage information to include reference to adjunctive CGM (E2102) and related supply allowance (A4238)
Added: Statement referring t […]

— `L33822` §Revision History Information ¶158

> ry of refills, the supplier must deliver the DMEPOS product no sooner than 10 calendar days prior to the expected end of the current supply."    *12/14/2023: Pursuant to the 21st Century Cures Act, these revisions do not require notice and comment because the revisions are non-discretionary updates to refill requirement information per CMS Final Rule CMS-1780-F.* | * Provider Education/Guidance * Other (CMS Final Rule CMS-1780-F) |
| 01/01/2024 | R13 | Revision Effective Date: 01/01/2024 COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY: Added: "or Medicare-approved telehealth" to Hi […]

— `L33822` §Revision History Information ¶144

> *12/14/2023: Pursuant to the 21st Century Cures Act, these revisions do not require notice and comment because the revisions are non-discretionary updates to refill requirement information per CMS Final Rule CMS-1780-F.*

— `L33822` §Revision History Information ¶150

### c2 (**must**)

Sources stating the requirement are superseded

> *12/14/2023: Pursuant to the 21st Century Cures Act, these revisions do not require notice and comment because the revisions are non-discretionary updates to refill requirement information per CMS Final Rule CMS-1780-F.*

— `L33822` §Revision History Information ¶150

> If you are experiencing any technical issues related to the search, selecting the 'OK' button to reset the search data should resolve your issues.

— `L33822` §Are you having technical issues with the Medicare Coverage Database (MCD)? ¶268

> ## Are you having technical issues with the Medicare Coverage Database (MCD)?

— `L33822` §Are you having technical issues with the Medicare Coverage Database (MCD)? ¶264

### c3 (**must**)

Current criteria are insulin treatment or problematic hypoglycemia

> tiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" as a CGM initial coverage criterion Removed: "The beneficiary is insulin-treated with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from […]

— `L33822` §Revision History Information ¶144

> Revision Effective Date: 04/16/2023
COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY:
Revised: Coverage criteria to separate initial coverage and continued coverage requirements
Removed: "with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated
Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" […]

— `L33822` §Revision History Information ¶153

> The beneficiary has a history of problematic hypoglycemia with documentation of at least one of the following (see the POLICY SPECIFIC DOCUMENTATION REQUIREMENTS section of the LCD-related Policy Article (A52464)):

— `L33822` §Coverage Guidance ¶72

## Required evidence key phrases

### e1 (**must**) — L33822 [LCD]

`Revision`

> ## Revision History Information

— `L33822` §Revision History Information ¶143

> Revision Effective Date: 10/01/2024
HCPCS CODES:
Revised: Long descriptor for HCPCS code A4271 in Group 2 Codes

— `L33822` §Revision History Information ¶145

> Revision Effective Date: 04/01/2024
HCPCS CODES:
Added: Codes E2104 to Group 1 Codes and A4271 to Group 2 Codes

— `L33822` §Revision History Information ¶147

`insulin`

> Revision Effective Date: 07/18/2021
COVERAGE INDICATIONS, LIMITATIONS AND/OR MEDICAL NECESSITY:
Removed: Four times or more per day testing with blood glucose monitor as prerequisite for CGM coverage
Revised: "injections" to "administrations" for insulin treatment regimen criterion for CGMs
Removed: "Medicare-covered" from CSII pump criterion language for CGMs
Clarified: Coding verification language for products billed as K0554
SUMMARY OF EVIDENCE:
Added: Information related to glucose testing and insulin administration
Revised: "5" to "1" minutes for measuring of interstitial fluid glucose co […]

— `L33822` §Revision History Information ¶160

> When a CGM (code E2102 or E2103) is covered, the related supply allowance (code A4238 or A4239) is also covered. Supplies (code A4238) for an adjunctive CGM integrated into an external insulin infusion pump are covered when the beneficiary meets both the CGM coverage criteria and the coverage criteria for an external insulin infusion pump. Refer to the External Infusion Pumps LCD (L33794) for additional information regarding billing a CGM receiver incorporated into an insulin infusion pump.

— `L33822` §Coverage Guidance ¶76

> Insulin does not exist in an oral form and therefore beneficiaries taking oral medication to treat their diabetes are not insulin-treated.

— `L33822` §Appendices ¶135

## Forbidden claims

- **f1**: Three or more daily injections are required — _superseded 2023_
