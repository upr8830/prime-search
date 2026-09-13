# cgm-elig-003 — validation worksheet

**What practitioner visit requirements must be met for initial and continued Medicare coverage of a CGM?**

`cgm` · tier 2 · eligibility · split `holdout`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Draft summary

Initial coverage requires an in-person or Medicare-approved telehealth visit with the treating practitioner within six months prior to ordering, to evaluate diabetes control and determine criteria are met. Continued coverage requires a visit every six months following the initial prescription to assess adherence to the CGM regimen and diabetes treatment plan.

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

A visit with the treating practitioner within six months before ordering is required

> Within six (6) months prior to ordering the CGM, the treating practitioner has an in-person or Medicare-approved telehealth visit with the beneficiary to evaluate their diabetes control and determined that criteria (1)-(4) above are met.

— `L33822` §Coverage Guidance ¶73

> Within the six (6) months prior to ordering quantities of strips and lancets that exceed the utilization guidelines, the treating practitioner has had an in-person or Medicare-approved telehealth visit with the beneficiary to evaluate their diabetes control and their need for the specific quantity of supplies that exceeds the usual utilization amounts described above; and,

— `L33822` §Coverage Guidance ¶60

> Every six (6) months following the initial prescription of the CGM, the treating practitioner conducts an in-person or Medicare-approved telehealth visit with the beneficiary to document adherence to their CGM regimen and diabetes treatment plan.

— `L33822` §Coverage Guidance ¶75

### c2 (**must**)

Follow-up visits every six months are required for continued coverage

> Every six (6) months, for continued dispensing of quantities of testing supplies that exceed the usual utilization amounts, the treating practitioner must verify adherence to the high utilization testing regimen.

— `L33822` §Coverage Guidance ¶61

> Every six (6) months following the initial prescription of the CGM, the treating practitioner conducts an in-person or Medicare-approved telehealth visit with the beneficiary to document adherence to their CGM regimen and diabetes treatment plan.

— `L33822` §Coverage Guidance ¶75

> For a beneficiary who is currently being treated with insulin administrations, up to 300 test strips and up to 300 lancets every 3 months are covered if basic coverage criteria (1)-(2) (above) are met.

— `L33822` §Coverage Guidance ¶55

### c3 (optional)

Telehealth visits are acceptable where Medicare-approved

> Within six (6) months prior to ordering the CGM, the treating practitioner has an in-person or Medicare-approved telehealth visit with the beneficiary to evaluate their diabetes control and determined that criteria (1)-(4) above are met.

— `L33822` §Coverage Guidance ¶73

> Every six (6) months following the initial prescription of the CGM, the treating practitioner conducts an in-person or Medicare-approved telehealth visit with the beneficiary to document adherence to their CGM regimen and diabetes treatment plan.

— `L33822` §Coverage Guidance ¶75

> Within the six (6) months prior to ordering quantities of strips and lancets that exceed the utilization guidelines, the treating practitioner has had an in-person or Medicare-approved telehealth visit with the beneficiary to evaluate their diabetes control and their need for the specific quantity of supplies that exceeds the usual utilization amounts described above; and,

— `L33822` §Coverage Guidance ¶60

## Required evidence key phrases

### e1 (**must**) — L33822 [LCD]

`six (6) months`

> Every six (6) months, for continued dispensing of quantities of testing supplies that exceed the usual utilization amounts, the treating practitioner must verify adherence to the high utilization testing regimen.

— `L33822` §Coverage Guidance ¶61

> Every six (6) months following the initial prescription of the CGM, the treating practitioner conducts an in-person or Medicare-approved telehealth visit with the beneficiary to document adherence to their CGM regimen and diabetes treatment plan.

— `L33822` §Coverage Guidance ¶75

> Within six (6) months prior to ordering the CGM, the treating practitioner has an in-person or Medicare-approved telehealth visit with the beneficiary to evaluate their diabetes control and determined that criteria (1)-(4) above are met.

— `L33822` §Coverage Guidance ¶73

`treating practitioner`

> An order renewal is the act of obtaining an order for an additional period of time beyond that previously ordered by the treating practitioner.

— `L33822` §Appendices ¶137

> Revision Effective Date: 01/01/2020
COVERAGE INDICATIONS, LIMITATIONS AND/OR MEDICAL NECESSITY:
Removed: Statement to refer to ICD-10 Codes that are Covered section in the LCD-related PA
Added: Statement to refer to ICD-10 code list in the LCD-related Policy Article
Revised: "physician" to "treating practitioner"
Revised: "treating physician" to "treating practitioner"
Revised: "month" to "30 days," as clarification of billing K0553
Revised: Format of HCPCS code references, from code spans to individually-listed HCPCS
Revised: Order information as a result of Final Rule 1713
 REFILL REQUIREMEN […]

— `L33822` §Revision History Information ¶161

> The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription; and,

— `L33822` §Coverage Guidance ¶68
