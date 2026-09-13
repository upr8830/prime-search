# cgm-elig-005 — validation worksheet

**Will Medicare cover a CGM for someone with prediabetes?**

`cgm` · tier 3 · eligibility · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Medicare covers CGM for anyone at risk of diabetes" — verify by hand

## Draft summary

No. LCD L33822 requires a diagnosis of diabetes mellitus and either insulin treatment or problematic hypoglycemia. Prediabetes does not meet the diagnosis requirement; some vendor and news pages imply broader coverage and should be treated as non-authoritative.

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

A diagnosis of diabetes mellitus is required

> The beneficiary has diabetes mellitus (Refer to the ICD-10 code list in the LCD-related Policy Article for applicable diagnoses); and,

— `L33822` §Coverage Guidance ¶67

> The quantity of test strips (code A4253) and lancets (code A4259) that are covered depends on the usual medical needs of the beneficiary and whether or not the beneficiary is being treated with insulin, regardless of their diagnostic classification as having Type 1 or Type 2 diabetes mellitus. Coverage of testing supplies is based on the following guidelines:

— `L33822` §Coverage Guidance ¶52

> Proof of delivery (POD) is a Supplier Standard and DMEPOS suppliers are required to maintain POD documentation in their files. Proof of delivery documentation must be made available to the Medicare contractor upon request. All services that do not have appropriate proof of delivery from the supplier shall be denied as not reasonable and necessary.

— `L33822` §Coverage Guidance ¶87

### c2 (**must**)

Prediabetes does not meet the coverage criteria

> To be eligible for coverage of a CGM and related supplies, the beneficiary must meet all of the following initial coverage criteria (1)-(5):

— `L33822` §Coverage Guidance ¶66

> To be eligible for coverage of home blood glucose monitors and related accessories and supplies, the beneficiary must meet both of the following basic criteria (1)-(2):

— `L33822` §Coverage Guidance ¶42

> If any of the initial coverage criteria (1)-(5), or the continued coverage criterion are not met, the CGM and related supply allowance will be denied as not reasonable and necessary.

— `L33822` §Coverage Guidance ¶77

## Required evidence key phrases

### e1 (**must**) — L33822 [LCD]

`diabetes mellitus`

> The beneficiary has diabetes mellitus (Refer to the ICD-10 code list in the LCD-related Policy Article for applicable diagnoses); and,

— `L33822` §Coverage Guidance ¶67

> The quantity of test strips (code A4253) and lancets (code A4259) that are covered depends on the usual medical needs of the beneficiary and whether or not the beneficiary is being treated with insulin, regardless of their diagnostic classification as having Type 1 or Type 2 diabetes mellitus. Coverage of testing supplies is based on the following guidelines:

— `L33822` §Coverage Guidance ¶52

> The beneficiary has diabetes (Refer to the ICD-10 code list in the LCD-related Policy Article for applicable diagnoses); and,

— `L33822` §Coverage Guidance ¶43

## Forbidden claims

- **f1**: Medicare covers CGM for anyone at risk of diabetes — _not in LCD_
