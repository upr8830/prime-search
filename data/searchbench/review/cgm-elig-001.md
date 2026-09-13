# cgm-elig-001 — validation worksheet

**Is a therapeutic CGM covered under Medicare for a type 2 diabetic who is not on insulin?**

`cgm` · tier 2 · eligibility · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [date] L33822 is now at 2024-10-01; the draft's 2023-04-16 is still in the document's revision history, so a claim *about that revision* is fine — check only that the key does not present it as current

## Draft summary

Yes, potentially. Under LCD L33822 a CGM is covered for a beneficiary with diabetes who is either treated with insulin OR has a history of problematic hypoglycemia (recurrent level 2 or at least one level 3 event) despite attempts to modify treatment, plus practitioner visit and documentation requirements. A non-insulin patient qualifies only through the hypoglycemia pathway.

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

Coverage requires treatment with insulin OR a documented history of problematic hypoglycemia

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

### c2 (**must**)

Problematic hypoglycemia means recurrent level 2 events or at least one level 3 event, despite multiple attempts to adjust medication or modify the treatment plan

> The beneficiary has a history of problematic hypoglycemia with documentation of at least one of the following (see the POLICY SPECIFIC DOCUMENTATION REQUIREMENTS section of the LCD-related Policy Article (A52464)):

— `L33822` §Coverage Guidance ¶72

> The beneficiary for whom a CGM is being prescribed, to improve glycemic control, meets at least one of the criteria below:

— `L33822` §Coverage Guidance ¶70

> Every six (6) months following the initial prescription of the CGM, the treating practitioner conducts an in-person or Medicare-approved telehealth visit with the beneficiary to document adherence to their CGM regimen and diabetes treatment plan.

— `L33822` §Coverage Guidance ¶75

### c3 (**must**)

The beneficiary must have a visit with the treating practitioner to evaluate diabetes control and determine CGM criteria are met within the required window before the order

> Within six (6) months prior to ordering the CGM, the treating practitioner has an in-person or Medicare-approved telehealth visit with the beneficiary to evaluate their diabetes control and determined that criteria (1)-(4) above are met.

— `L33822` §Coverage Guidance ¶73

> Within the six (6) months prior to ordering quantities of strips and lancets that exceed the utilization guidelines, the treating practitioner has had an in-person or Medicare-approved telehealth visit with the beneficiary to evaluate their diabetes control and their need for the specific quantity of supplies that exceeds the usual utilization amounts described above; and,

— `L33822` §Coverage Guidance ¶60

> Every six (6) months following the initial prescription of the CGM, the treating practitioner conducts an in-person or Medicare-approved telehealth visit with the beneficiary to document adherence to their CGM regimen and diabetes treatment plan.

— `L33822` §Coverage Guidance ¶75

### c4 (optional)

The non-insulin pathway was introduced by the LCD revision effective April 16, 2023

> A Local Coverage Determination (LCD) is a decision made by a Medicare Administrative Contractor (MAC) on whether a particular service or item is reasonable and necessary, and therefore covered by Medicare within the specific jurisdiction that the MAC oversees.

— `L33822` §Introduction ¶213

> For the items addressed in this LCD, the "reasonable and necessary" criteria, based on Social Security Act § 1862(a)(1)(A) provisions, are defined by the following coverage indications, limitations and/or medical necessity.

— `L33822` §Coverage Guidance ¶40

> Revision Effective Date: 02/28/2022
HCPCS CODES:
Revised: Location of E2102 information, moving the information from Group 1 Paragraph text to Group 1 Codes HCPCS list (code remains effective for dates of service on or after 04/01/2022)
Revised: Location of A4238 information, moving the information from Group 2 Paragraph text to Group 2 Codes HCPCS list (code remains effective for dates of service on or after 04/01/2022)

— `L33822` §Revision History Information ¶156

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

- **f1**: Multiple daily injections (three or more) are required — _requirement removed by the 2023 revision_
