# cgm-elig-004 — validation worksheet

**Does Medicare cover a CGM for a type 1 diabetic using an insulin pump?**

`cgm` · tier 1 · eligibility · split `dev`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Draft summary

Yes. A beneficiary with diabetes treated with insulin (including via pump) meets the treatment criterion of LCD L33822; the visit and documentation requirements still apply.

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

Insulin treatment satisfies the LCD's treatment criterion regardless of delivery method

> tiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" as a CGM initial coverage criterion Removed: "The beneficiary is insulin-treated with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from […]

— `L33822` §Revision History Information ¶144

> Revision Effective Date: 04/16/2023
COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY:
Revised: Coverage criteria to separate initial coverage and continued coverage requirements
Removed: "with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated
Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" […]

— `L33822` §Revision History Information ¶153

> For DMEPOS items and supplies provided on a recurring basis, billing must be based on prospective, not retrospective use. For DMEPOS products that are supplied as refills to the original order, suppliers must contact the beneficiary, and document an affirmative response, prior to dispensing the refill and not automatically ship on a pre-determined basis, even if authorized by the beneficiary. This shall be done to ensure that the refilled item remains reasonable and necessary, existing supplies are expected to end, and to confirm any changes or modifications to the order. Contact with the bene […]

— `L33822` §Coverage Guidance ¶89

### c2 (**must**)

Visit and documentation requirements still apply

> **DOCUMENTATION REQUIREMENTS**

— `L33822` §DOCUMENTATION REQUIREMENTS ¶120

> **GENERAL DOCUMENTATION REQUIREMENTS**

— `L33822` §GENERAL DOCUMENTATION REQUIREMENTS ¶122

> **POLICY SPECIFIC DOCUMENTATION REQUIREMENTS**

— `L33822` §POLICY SPECIFIC DOCUMENTATION REQUIREMENTS ¶131

## Required evidence key phrases

### e1 (**must**) — L33822 [LCD]

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
