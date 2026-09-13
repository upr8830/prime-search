# chg-cgm-001 — validation worksheet

**What changed in Medicare CGM coverage criteria in 2023?**

`cgm` · tier 2 · change_detection · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [date] L33822 is now at 2024-10-01; the draft's 2023-04-16 is still in the document's revision history, so a claim *about that revision* is fine — check only that the key does not present it as current
- [date] A52464 is now at 2025-02-18; the draft's 2023-04-16 is still in the document's revision history, so a claim *about that revision* is fine — check only that the key does not present it as current
- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Changes took effect in 2022" — verify by hand

## Draft summary

The LCD revision effective April 16, 2023 removed the requirement of multiple daily insulin injections and extended coverage to any insulin-treated beneficiary and to non-insulin beneficiaries with problematic hypoglycemia; the coding article moved to E2102/E2103 and A4238/A4239.

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs
- `A52464` via **record_url** — [Glucose Monitor - Policy Article (A52464) - CMS](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464) · primary_policy · 2025-02-18 · 281 paragraphs

## Required claims, against the live text

### c1 (**must**)

The revision effective April 16, 2023 expanded eligibility to all insulin-treated patients

> Revision Effective Date: 01/01/2019
ICD-10 CODES THAT ARE COVERED:
Added: All diagnosis codes formerly listed in the LCD
ICD-10 CODES THAT ARE NOT COVERED:
Added: Notation excluding all unlisted diagnosis codes from coverage

— `A52464` §Revision History Information ¶165

> after January 1, 2023, a non-adjunctive CGM must be billed with code E2103 and code A4239 for the supply allowance."  Added: HCPCS code E2103 to description of non-adjunctive CGM that meets DME benefit requirements Added: HCPCS code A4239 to supply allowance language Removed: HCPCS code K0553 from supply allowance language  Added: HCPCS code A4239 to delivery and billing language Removed: HCPCS code K0553 from delivery and billing language Added: Billing instructions for dates of service prior to April 1, 2022, and on or after January 1, 2023, for HCPCS codes A9276 and A9277 to describe suppli […]

— `A52464` §Revision History Information ¶140

> For dates of service prior to April 1, 2022, and dates of service on or after January 1, 2023, code A9278 (RECEIVER (MONITOR); EXTERNAL, FOR USE WITH NON-DURABLE MEDICAL EQUIPMENT INTERSTITIAL CONTINUOUS GLUCOSE MONITORING SYSTEM) describes any CGM system that fails to meet the DME Benefit requirements as described under the NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES section.

— `A52464` §CODING GUIDELINES ¶82

### c2 (**must**)

A non-insulin pathway based on problematic hypoglycemia was added

> Revision Effective Date: 01/12/2017
NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES:
Added: Date of inclusion in DME benefit
CODING GUIDELINES:
Added: Coding information for CGM, based on date of service

— `A52464` §Revision History Information ¶169

> For criterion 4B, the treating practitioner's medical record must document the beneficiary has a history of problematic hypoglycemia consistent with one of the following pathways to coverage:

— `A52464` §POLICY SPECIFIC DOCUMENTATION REQUIREMENTS ¶58

> The beneficiary has a history of problematic hypoglycemia with documentation of at least one of the following (see the POLICY SPECIFIC DOCUMENTATION REQUIREMENTS section of the LCD-related Policy Article (A52464)):

— `L33822` §Coverage Guidance ¶72

### c3 (optional)

New HCPCS codes E2102/E2103 and A4238/A4239 took effect in 2023

> after January 1, 2023, a non-adjunctive CGM must be billed with code E2103 and code A4239 for the supply allowance."  Added: HCPCS code E2103 to description of non-adjunctive CGM that meets DME benefit requirements Added: HCPCS code A4239 to supply allowance language Removed: HCPCS code K0553 from supply allowance language  Added: HCPCS code A4239 to delivery and billing language Removed: HCPCS code K0553 from delivery and billing language Added: Billing instructions for dates of service prior to April 1, 2022, and on or after January 1, 2023, for HCPCS codes A9276 and A9277 to describe suppli […]

— `A52464` §Revision History Information ¶140

> Revision Effective Date: 01/01/2023
CONTINUOUS GLUCOSE MONITORS (CGM):
Removed: Statement regarding general CGM term referring to both therapeutic/non-adjunctive and non-therapeutic/adjunctive
Removed: "therapeutic" and "non-therapeutic"
Removed: HCPCS codes K0554 and K0553
Added: HCPCS codes E2103 and A4239
REFILL REQUIREMENTS:
Removed: HCPCS code K0553
Added: HCPCS code A4239
HCPCS CODES:
Revised: Long descriptor for HCPCS code E2102 in Group 1 Codes
Added: HCPCS code E2103 to Group 1 Codes
Removed: HCPCS code K0554 from Group 1 Codes
Revised: Long descriptor for HCPCS code A4238 in Group 2 […]

— `L33822` §Revision History Information ¶154

> fit requirements
Added: HCPCS code A4239 to supply allowance language
Removed: HCPCS code K0553 from supply allowance language
Added: HCPCS code A4239 to delivery and billing language
Removed: HCPCS code K0553 from delivery and billing language
Added: Billing instructions for dates of service prior to April 1, 2022, and on or after January 1, 2023, for HCPCS codes A9276 and A9277 to describe supplies used with a CGM that does not meet the definition of DME
Added: Instructions not to bill HCPCS codes A9276 and A9277 for supplies used with a non-adjunctive CGM (E2103) or adjunctive CGM supplies […]

— `A52464` §Revision History Information ¶155

## Required evidence key phrases

### e1 (**must**) — L33822 [LCD]

`04/16/2023`

> testing sufficient to perform ten (10) blood glucose tests. The "per month" HCPCS descriptor represents one (1) unit of service (UOS) of code A4271 and is equivalent to 100 test strips and 100 lancets." Added: Code E2104 to Column I and A4233, A4234, A4235, A4236 to corresponding Column II  ICD-10-CM CODES THAT SUPPORT MEDICAL NECESSITY: Added: ICD-10-CM codes E11.10 and E11.11 to Group 1 Codes (Effective for claims with dates of service on or after October 1, 2017)  *05/02/2024: At this time the 21st Century Cures Act applies to new and revised LCDs which require comment and notice. This revi […]

— `A52464` §Revision History Information ¶140

> ry of refills, the supplier must deliver the DMEPOS product no sooner than 10 calendar days prior to the expected end of the current supply."    *12/14/2023: Pursuant to the 21st Century Cures Act, these revisions do not require notice and comment because the revisions are non-discretionary updates to refill requirement information per CMS Final Rule CMS-1780-F.* | * Provider Education/Guidance * Other (CMS Final Rule CMS-1780-F) |
| 01/01/2024 | R13 | Revision Effective Date: 01/01/2024 COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY: Added: "or Medicare-approved telehealth" to Hi […]

— `L33822` §Revision History Information ¶144

> Revision Effective Date: 04/16/2023
POLICY SPECIFIC DOCUMENTATION REQUIREMENTS:
Added: "or Medicare-approved telehealth" to the in-person visit requirement as part of the initial and ongoing provision of a CGM
Removed: Language from criterion 1 regarding frequent dosing of insulin
Added: Language to criterion 1 regarding appropriate training received in the use of the CGM is evidenced by a prescription
Removed: Language from criterion 2 regarding frequent adjustment of diabetes treatment regimen
Added: Language to criterion 2 regarding the CGM is prescribed in accordance with FDA indications f […]

— `A52464` §Revision History Information ¶153

`Revision`

> ## Revision History Information

— `L33822` §Revision History Information ¶143

> ## Revision History Information

— `A52464` §Revision History Information ¶139

> Revision Effective Date: 10/01/2024
HCPCS CODES:
Revised: Long descriptor for HCPCS code A4271 in Group 2 Codes

— `L33822` §Revision History Information ¶145

## Forbidden claims

- **f1**: Changes took effect in 2022 — _wrong year_
