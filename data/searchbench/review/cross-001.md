# cross-001 — validation worksheet

**A Medicare beneficiary takes a GLP-1 for type 2 diabetes but no insulin. Can they get a covered CGM?**

`cross` · tier 3 · eligibility · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Draft summary

Only via the problematic-hypoglycemia pathway of LCD L33822 (recurrent level 2 or one level 3 event despite treatment changes), since GLP-1 therapy alone does not satisfy the insulin criterion. GLP-1 coverage itself is a Part D matter and unrelated to the CGM DME benefit.

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

GLP-1 therapy does not satisfy the insulin criterion

> Insulin does not exist in an oral form and therefore beneficiaries taking oral medication to treat their diabetes are not insulin-treated.

— `L33822` §Appendices ¶135

> tiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" as a CGM initial coverage criterion Removed: "The beneficiary is insulin-treated with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from […]

— `L33822` §Revision History Information ¶144

> Revision Effective Date: 04/16/2023
COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY:
Revised: Coverage criteria to separate initial coverage and continued coverage requirements
Removed: "with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated
Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" […]

— `L33822` §Revision History Information ¶153

### c2 (**must**)

Coverage is possible through the problematic-hypoglycemia pathway

> In order for CMS to change billing and claims processing systems to accommodate the coverage conditions within the NCD, we instruct contractors and system maintainers to modify the claims processing systems at the national or local level through CR Transmittals. CRs are not policy, rather CRs are used to relay instructions regarding the edits of the various claims processing systems in very descriptive, technical language usually employing the codes or code combinations likely to be encountered with claims subject to the policy in question. As clinical or administrative codes change or system […]

— `L33822` §National Coverage ¶252

> The beneficiary is insulin-treated; or,

— `L33822` §Coverage Guidance ¶71

> Code E2101 is also covered for those with impairment of manual dexterity when the basic coverage criteria (1)-(2) are met and the treating practitioner certifies that the beneficiary has an impairment of manual dexterity severe enough to require the use of this special monitoring system. Coverage of code E2101 for beneficiaries with manual dexterity impairments is not dependent upon a visual impairment.

— `L33822` §Coverage Guidance ¶47

### c3 (optional)

GLP-1 (Part D) and CGM (Part B DME) are separate benefits

> The guidelines for LCD development are provided in Chapter 13 of the Medicare Program Integrity Manual. The Social Security Act, Sections 1869(f)(2)(B) and 1862(l)(5)(D) define LCDs and provide information on the process.

— `L33822` §More information ¶220

> A non-adjunctive CGM can be used to make treatment decisions without the need for a stand-alone BGM to confirm testing results. An adjunctive CGM requires the user verify their glucose levels or trends displayed on a CGM with a BGM prior to making treatment decisions. On February 28, 2022, CMS determined that both non-adjunctive and adjunctive CGMs may be classified as DME.

— `L33822` §Coverage Guidance ¶64

> Revision Effective Date: 04/16/2023
COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY:
Revised: Coverage criteria to separate initial coverage and continued coverage requirements
Removed: "with multiple (three or more) daily administrations of insulin or a continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion pertaining to beneficiary being insulin-treated
Added: "The beneficiary's treating practitioner has concluded that the beneficiary (or beneficiary's caregiver) has sufficient training using the CGM prescribed as evidenced by providing a prescription" […]

— `L33822` §Revision History Information ¶153

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
