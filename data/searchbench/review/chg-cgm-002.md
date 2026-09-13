# chg-cgm-002 — validation worksheet

**Are there any proposed or recently finalized revisions to the Medicare glucose monitor LCD (L33822) as of today?**

`cgm` · tier 3 · change_detection · split `dev`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [authoring] docs/08 §4: a change-detection key must list the changes with dates, but asserts none

## Draft summary

Answer from the current CMS coverage database: the LCD's current revision date, any proposed LCD (DL-number) open for comment, and any future effective date. If none, say so with the date checked.

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

The current revision effective date of L33822 is stated

> | Revision History Date | Revision History Number | Revision History Explanation | Reasons for Change |
| --- | --- | --- | --- |
| 10/01/2024 | R16 | Revision Effective Date: 10/01/2024 HCPCS CODES: Revised: Long descriptor for HCPCS code A4271 in Group 2 Codes  *10/17/2024: Pursuant to the 21st Century Cures Act, these revisions do not require notice and comment because the revisions are non-discretionary updates per CMS HCPCS coding determinations.* | * Provider Education/Guidance * Revisions Due To CPT/HCPCS Code Changes |
| 04/01/2024 | R15 | Revision Effective Date: 04/01/2024 HCPCS CODE […]

— `L33822` §Revision History Information ¶144

> Revision Effective Date: 01/01/2024
COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY:
Added: "and document an affirmative response" to language that pertains to contact with the beneficiary or caregiver/designee for DMEPOS products supplied as refills
Revised: "approaching exhaustion" to "expected to end" in regard to existing supplies
Revised: "Contact with the beneficiary or designee regarding refills must take place no sooner than 14 calendar days prior to the delivery/shipping date." to "Contact with the beneficiary or designee regarding refills must take place no sooner than 30 […]

— `L33822` §Revision History Information ¶149

> Revision Effective Date: 02/28/2022
HCPCS CODES:
Revised: Location of E2102 information, moving the information from Group 1 Paragraph text to Group 1 Codes HCPCS list (code remains effective for dates of service on or after 04/01/2022)
Revised: Location of A4238 information, moving the information from Group 2 Paragraph text to Group 2 Codes HCPCS list (code remains effective for dates of service on or after 04/01/2022)

— `L33822` §Revision History Information ¶156

### c2 (**must**)

Whether a proposed revision exists is stated with the date checked

> A Local Coverage Determination (LCD) is a decision made by a Medicare Administrative Contractor (MAC) on whether a particular service or item is reasonable and necessary, and therefore covered by Medicare within the specific jurisdiction that the MAC oversees.

— `L33822` §Introduction ¶213

> If a glucose monitor (code E2100 or E2101) is provided and basic coverage criteria (1)-(2) plus the additional criteria stated above are not met, it will be denied as not reasonable and necessary.

— `L33822` §Coverage Guidance ¶48

> The quantity of test strips (code A4253) and lancets (code A4259) that are covered depends on the usual medical needs of the beneficiary and whether or not the beneficiary is being treated with insulin, regardless of their diagnostic classification as having Type 1 or Type 2 diabetes mellitus. Coverage of testing supplies is based on the following guidelines:

— `L33822` §Coverage Guidance ¶52

## Required evidence key phrases

### e1 (**must**) — L33822 [LCD]

`Revision Effective Date`

> Revision Effective Date: 10/01/2024
HCPCS CODES:
Revised: Long descriptor for HCPCS code A4271 in Group 2 Codes

— `L33822` §Revision History Information ¶145

> Revision Effective Date: 04/01/2024
HCPCS CODES:
Added: Codes E2104 to Group 1 Codes and A4271 to Group 2 Codes

— `L33822` §Revision History Information ¶147

> Revision Effective Date: 01/12/2017
COVERAGE INDICATIONS, LIMITATIONS AND/OR MEDICAL NECESSITY:
CPT/HCPCS Codes:
Revised: Incorporated K0554 into Group 1 Codes and HCPCS code K0553 into Group 2 Codes

— `L33822` §Revision History Information ¶164
