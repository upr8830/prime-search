# cross-003 — validation worksheet

**If a non-insulin type 2 patient starts a GLP-1 and later has severe hypoglycemia, could that make them eligible for a Medicare-covered CGM?**

`cross` · tier 3 · eligibility · split `holdout`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Draft summary

Potentially. Eligibility depends on the LCD's problematic-hypoglycemia criterion — recurrent level 2 or one level 3 event, despite multiple attempts to adjust medication or modify the plan — documented by the treating practitioner; the cause of hypoglycemia is not itself a criterion. The answer should not advise on the patient's care.

## Expected scope warning

Policy-level answer only; not a determination for an individual

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

The problematic-hypoglycemia criterion can be met regardless of which medication contributed

> If any of the initial coverage criteria (1)-(5), or the continued coverage criterion are not met, the CGM and related supply allowance will be denied as not reasonable and necessary.

— `L33822` §Coverage Guidance ¶77

> If neither basic coverage criterion (1) or (2) is met, all testing supplies will be denied as not reasonable and necessary. If quantities of test strips or lancets that exceed the utilization guidelines are provided and criteria (a)-(c) are not met, the amount in excess will be denied as not reasonable and necessary.

— `L33822` §Coverage Guidance ¶62

> In addition to the "reasonable and necessary" criteria contained in this LCD there are other payment rules, which are discussed in the following documents, that must also be met prior to Medicare reimbursement:

— `L33822` §Coverage Guidance ¶35

### c2 (**must**)

Documentation by the treating practitioner is required

> An order renewal is the act of obtaining an order for an additional period of time beyond that previously ordered by the treating practitioner.

— `L33822` §Appendices ¶137

> The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription; and,

— `L33822` §Coverage Guidance ¶68

> The beneficiary's treating practitioner has concluded that the beneficiary (or the beneficiary's caregiver) has sufficient training using the particular device prescribed as evidenced by providing a prescription for the appropriate supplies and frequency of blood glucose testing.

— `L33822` §Coverage Guidance ¶44

## Required evidence key phrases

### e1 (**must**) — L33822 [LCD]

`problematic hypoglycemia`

> The beneficiary has a history of problematic hypoglycemia with documentation of at least one of the following (see the POLICY SPECIFIC DOCUMENTATION REQUIREMENTS section of the LCD-related Policy Article (A52464)):

— `L33822` §Coverage Guidance ¶72

> Revision Effective Date: 04/16/2023
COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY:
Revised: Coverage criteria to separate initial coverage and continued coverage requirements
Removed: "with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated
Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" […]

— `L33822` §Revision History Information ¶153

> tiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" as a CGM initial coverage criterion Removed: "The beneficiary is insulin-treated with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from […]

— `L33822` §Revision History Information ¶144
