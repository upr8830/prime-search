# adv-cgm-001 — validation worksheet

**Is a CGM covered by Medicare for gestational diabetes?**

`cross` · tier 4 · contradiction · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Medicare covers CGM for all gestational diabetes" — verify by hand

## Draft summary

The LCD covers beneficiaries with a diagnosis of diabetes mellitus who meet the insulin or problematic-hypoglycemia criteria; it does not carve out gestational diabetes, so coverage depends on meeting those criteria (e.g., insulin-treated GDM). Several secondary sources state or imply blanket coverage; the LCD text governs. Note that Medicare beneficiaries with GDM are uncommon.

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

Coverage depends on meeting the LCD's diabetes diagnosis plus insulin or hypoglycemia criteria

> The quantity of test strips (code A4253) and lancets (code A4259) that are covered depends on the usual medical needs of the beneficiary and whether or not the beneficiary is being treated with insulin, regardless of their diagnostic classification as having Type 1 or Type 2 diabetes mellitus. Coverage of testing supplies is based on the following guidelines:

— `L33822` §Coverage Guidance ¶52

> tiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" as a CGM initial coverage criterion Removed: "The beneficiary is insulin-treated with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from […]

— `L33822` §Revision History Information ¶144

> Revision Effective Date: 04/16/2023
COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY:
Revised: Coverage criteria to separate initial coverage and continued coverage requirements
Removed: "with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated
Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" […]

— `L33822` §Revision History Information ¶153

### c2 (**must**)

Secondary sources that state blanket coverage conflict with the LCD and the LCD governs

> Enter the CPT/HCPCS code in the [MCD Search](https://www.cms.gov/medicare-coverage-database/new-search/search.aspx) and select your state from the drop down. (You may have to accept the AMA License Agreement.) Look for a Billing and Coding Article in the results and open it. (Or, for DME MACs only, look for an LCD.) Review the article, in particular the Coding Information section.

— `L33822` §How do I find out if a specific CPT code is covered in my state? ¶254

> LCD document IDs begin with the letter "L" (e.g., L12345). Proposed LCD document IDs begin with the letters "DL" (e.g., DL12345).

— `L33822` §More information ¶219

> The LCD Tracking Sheet is a pop-up modal that is displayed on top of any Proposed LCD that began to appear on the MCD on or after 1/1/2022.

— `L33822` §Tracking Sheet ¶222

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

- **f1**: Medicare covers CGM for all gestational diabetes — _not in LCD_
