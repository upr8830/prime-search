# cgm-code-001 — validation worksheet

**What HCPCS codes apply to a therapeutic (non-adjunctive) CGM receiver and its supplies under Medicare?**

`cgm` · tier 2 · coding · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Bill CGM supplies with K0553" — verify by hand
- [code] K0553 is called stale by a forbidden_claim but still appears in the live document — confirm before penalising an answer that uses it

## Draft summary

Per the coding article A52464, the non-adjunctive CGM receiver is billed with E2103 and the monthly supply allowance with A4239; adjunctive CGMs use E2102 and A4238. Older codes K0554/K0553 were replaced in 2023.

## Governing documents

- `A52464` via **record_url** — [Glucose Monitor - Policy Article (A52464) - CMS](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464) · primary_policy · 2025-02-18 · 281 paragraphs

## Required claims, against the live text

### c1 (**must**)

Non-adjunctive CGM receiver: E2103; supplies: A4239

> For claims with dates of service on or after July 1, 2017, through December 31, 2022, a non-adjunctive CGM must be billed with code K0554 and code K0553 for the supply allowance. For claims with dates of service on or after January 1, 2023, a non-adjunctive CGM must be billed with code E2103 and code A4239 for the supply allowance. Code E2103 or K0554 describes a non-adjunctive CGM that meets the requirements of the DME benefit.

— `A52464` §CODING GUIDELINES ¶74

> after January 1, 2023, a non-adjunctive CGM must be billed with code E2103 and code A4239 for the supply allowance."  Added: HCPCS code E2103 to description of non-adjunctive CGM that meets DME benefit requirements Added: HCPCS code A4239 to supply allowance language Removed: HCPCS code K0553 from supply allowance language  Added: HCPCS code A4239 to delivery and billing language Removed: HCPCS code K0553 from delivery and billing language Added: Billing instructions for dates of service prior to April 1, 2022, and on or after January 1, 2023, for HCPCS codes A9276 and A9277 to describe suppli […]

— `A52464` §Revision History Information ¶140

> fit requirements
Added: HCPCS code A4239 to supply allowance language
Removed: HCPCS code K0553 from supply allowance language
Added: HCPCS code A4239 to delivery and billing language
Removed: HCPCS code K0553 from delivery and billing language
Added: Billing instructions for dates of service prior to April 1, 2022, and on or after January 1, 2023, for HCPCS codes A9276 and A9277 to describe supplies used with a CGM that does not meet the definition of DME
Added: Instructions not to bill HCPCS codes A9276 and A9277 for supplies used with a non-adjunctive CGM (E2103) or adjunctive CGM supplies […]

— `A52464` §Revision History Information ¶155

### c2 (optional)

Adjunctive CGM receiver: E2102; supplies: A4238

> Adjunctive CGM devices coded E2102 and related supplies coded A4238 are classified by the FDA as Class III; therefore, all claims for codes E2102 and A4238 must include the KF modifier. Claim lines billed without a KF modifier will be rejected as missing information.

— `A52464` §MODIFIERS ¶71

> Revision Effective Date: 02/28/2022
NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES:
Removed: Reference to CMS Ruling 1682R
Removed: "therapeutic" from the DME benefit statement
Added: Information regarding classification of CGMs as DME
Added: "CGM devices that solely display results on a smartphone and do not have a stand-alone receiver or integration into an insulin infusion pump do not meet the definition of DME and will be denied as non-covered (no benefit)."
Added: Supply allowance HCPCS code A4238 to billing information
Added: HCPCS codes A4238 and E2102 to supply allowance statements
R […]

— `A52464` §Revision History Information ¶159

> Coverage of a CGM system supply allowance (code A4238 or A4239) is available for CGM systems when the beneficiary uses a stand-alone receiver or insulin infusion pump classified as DME to display glucose data. In addition, Medicare coverage is available for a CGM system supply allowance if a non-DME device (watch, smartphone, tablet, laptop computer, etc.) is used in conjunction with the durable CGM receiver (code E2102 or E2103). The following are examples of this provision:

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶35

### c3 (optional)

K0553/K0554 are no longer the current codes

> For the most part, codes are no longer included in the LCD (policy). You will find them in the Billing & Coding Articles. Try using the [MCD Search](https://www.cms.gov/medicare-coverage-database/new-search/search.aspx) to find what you're looking for. Enter the code you're looking for in the "Enter keyword, code, or document ID" box. The list of results will include documents which contain the code you entered.

— `A52464` §Local Coverage ¶254

> American Medical Association Current Procedural Terminology

— `A52464` §Keywords ¶186

> American Dental Association Current Dental Terminology

— `A52464` §Keywords ¶187

## Required evidence key phrases

### e1 (**must**) — A52464 [Article]

`E2103`

> Nonadjunctive CGM devices coded E2103 and related supplies coded A4239 encompass both devices classified by the FDA as Class III and devices otherwise classified by the FDA. If Class III, then claims for codes E2103 and A4239 must include the KF modifier. If not Class III, then claims for codes E2103 and A4239 must not include the KF modifier. If uncertain whether the specific device is Class III, the supplier should confirm classification with the FDA or manufacturer prior to billing.

— `A52464` §MODIFIERS ¶72

> Revision Effective Date: 01/01/2023
NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES:
Added: "(non-adjunctive)" to coverage of claims with dates of service on or after January 12, 2017
Removed: "therapeutic" and "non-therapeutic" from testing language
Added: HCPCS code A4239 to supply allowance language
Removed: HCPCS code K0553 from supply allowance language
Added: HCPCS code E2103 to coverage of a CGM supply allowance language
Removed: HCPCS code K0554 from coverage of a CGM supply allowance language
Removed: HCPCS code K0554 from the coding verification review by the PDAC language
Added: HC […]

— `A52464` §Revision History Information ¶155

> time the 21st Century Cures Act applies to new and revised LCDs which require comment and notice. This revision is to an article that is not a local coverage determination.* |
| 01/01/2023 | R12 | Revision Effective Date: 01/01/2023 NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES: Added: "(non-adjunctive)" to coverage of claims with dates of service on or after January 12, 2017  Removed: "therapeutic" and "non-therapeutic" from testing language Added: HCPCS code A4239 to supply allowance language Removed: HCPCS code K0553 from supply allowance language Added: HCPCS code E2103 to coverage of a […]

— `A52464` §Revision History Information ¶140

`A4239`

> Nonadjunctive CGM devices coded E2103 and related supplies coded A4239 encompass both devices classified by the FDA as Class III and devices otherwise classified by the FDA. If Class III, then claims for codes E2103 and A4239 must include the KF modifier. If not Class III, then claims for codes E2103 and A4239 must not include the KF modifier. If uncertain whether the specific device is Class III, the supplier should confirm classification with the FDA or manufacturer prior to billing.

— `A52464` §MODIFIERS ¶72

> Revision Effective Date: 01/01/2024
CODING GUIDELINES:
Removed: Language regarding billing only one (1) month, thirty (30) days of the supply allowance for code A4238 or A4239
Added: Language regarding billing up to a maximum of three (3) months, ninety (90) days of the supply allowance for code A4238 or A4239

— `A52464` §Revision History Information ¶151

> The supply allowance for supplies used with a CGM system (A4238, A4239) encompasses all items necessary for the use of the device and includes but is not limited to, CGM sensors and transmitters. For non-adjunctive CGMs, the supply allowance (A4239) also includes a home BGM and related supplies (test strips, lancets, lancing device, calibration solution, and batteries), if necessary. Supplies or accessories billed separately will be denied as unbundling.

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶33

## Forbidden claims

- **f1**: Bill CGM supplies with K0553 — _code retired_
