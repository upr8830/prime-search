# cgm-code-003 — validation worksheet

**Where are the HCPCS coding and billing rules for Medicare CGM coverage published — in the LCD or somewhere else?**

`cgm` · tier 1 · coding · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Draft summary

Coding, billing, and documentation specifics are in the policy article A52464 (Glucose Monitors — Policy Article), which accompanies LCD L33822; the LCD contains the medical necessity criteria.

## Governing documents

- `A52464` via **record_url** — [Glucose Monitor - Policy Article (A52464) - CMS](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464) · primary_policy · 2025-02-18 · 281 paragraphs
- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

Coding and billing rules are in the policy article, not the LCD

> Articles which directly support an LCD are known as **"LCD Reference Articles"**.
The referenced LCD may be cited in the Article Text field and may also be linked to in the Related Documents field.
Examples may include but are not limited to Response to Comments and some Billing and Coding Articles.
If you have a question about this kind of article, please contact the MAC listed within the Contractor Information section of the article.

— `A52464` §Keywords ¶183

> Articles which directly support an LCD are known as "LCD Reference Articles". The referenced LCD may be cited in the Article Text field and may also be linked to in the Related Documents field. Examples may include but are not limited to Response to Comments and some Billing and Coding Articles. If you have a question about this kind of article, please contact the MAC listed within the Contractor Information section of the article.

— `A52464` §More information ¶226

> Refer to the NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES and CODING GUIDELINES sections in the LCD-related Policy Article for additional information regarding classification of CGMs as DME.

— `L33822` §Coverage Guidance ¶65

### c2 (**must**)

The LCD holds the coverage/medical-necessity criteria

> The CG modifier must be added to the claim line for an adjunctive CGM (E2102) incorporated into an insulin infusion pump and supply allowance (code A4238) only if all of the initial CGM coverage criteria (1)-(5) in the Glucose Monitors LCD and the coverage criteria for an insulin infusion pump as outlined in the External Infusion Pumps LCD (L33794) are met. For continued coverage of adjunctive CGM devices incorporated into an insulin infusion pump (code E2102) and the supply allowance (code A4238), the CG modifier must be added to the claim line only if the continued coverage criteria in the G […]

— `A52464` §MODIFIERS ¶70

> For initial coverage of non-adjunctive CGM devices (code E2103) and the supply allowance (code A4239) the CG modifier must be added to the claim line only if all of the CGM coverage criteria (1)-(5) in the Glucose Monitors LCD are met. For continued coverage of non-adjunctive CGM devices (code E2103) and the supply allowance (code A4239) the CG modifier must be added to the claim line only if the continued coverage criterion in the Glucose Monitors LCD is met. If any of the coverage criteria are not met, the CG modifier must not be used.

— `A52464` §MODIFIERS ¶69

> The presence of an ICD-10 code listed in this section is not sufficient by itself to assure coverage. Refer to the LCD section on "**Coverage Indications, Limitations, and/or Medical Necessity**" for other coverage criteria and payment information.

— `A52464` §Group 1 ¶113

## Required evidence key phrases

### e1 (**must**) — A52464 [Article]

`Policy Article`

> # Glucose Monitor - Policy Article

— `A52464` §Glucose Monitor - Policy Article ¶14

> Refer to the LCD-related Standard Documentation Requirements article (A55426), located at the bottom of this Policy Article under the Related Local Coverage Documents section, for additional information regarding GENERAL DOCUMENTATION REQUIREMENTS and the POLICY SPECIFIC DOCUMENTATION REQUIREMENTS discussed below.

— `A52464` §POLICY SPECIFIC DOCUMENTATION REQUIREMENTS ¶52

> A52464

— `A52464` §Glucose Monitor - Policy Article ¶15

`HCPCS`

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
