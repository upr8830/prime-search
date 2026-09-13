# cgm-elig-006 — validation worksheet

**Can a nurse practitioner order a CGM under Medicare, and what must the order contain?**

`cgm` · tier 2 · eligibility · split `holdout`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [key_phrase] e2 (A52464): standard written order not found in the live document

## Draft summary

Yes; the LCD refers to the 'treating practitioner', which under Medicare DME rules includes physicians and non-physician practitioners such as NPs and PAs within their scope of practice. A standard written order meeting DME requirements is needed, and the medical record must document the coverage criteria.

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs
- `A52464` via **record_url** — [Glucose Monitor - Policy Article (A52464) - CMS](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464) · primary_policy · 2025-02-18 · 281 paragraphs

## Required claims, against the live text

### c1 (**must**)

The treating practitioner may be a physician or a non-physician practitioner such as an NP or PA

> The treating practitioner has had an in-person or Medicare-approved telehealth visit to evaluate the beneficiary's diabetes control; and,

— `A52464` §POLICY SPECIFIC DOCUMENTATION REQUIREMENTS ¶54

> For the in-person or Medicare-approved telehealth treating practitioner visit that is required as part of the ongoing provision of a CGM, there must be sufficient information in the beneficiary's medical record to determine that the beneficiary continues to adhere to their diabetes treatment regimen and use of the CGM device.

— `A52464` §POLICY SPECIFIC DOCUMENTATION REQUIREMENTS ¶59

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

### c2 (**must**)

A standard written order is required

> Final Rule 1713 (84 Fed. Reg Vol 217) requires a face-to-face encounter and a Written Order Prior to Delivery (WOPD) for specified HCPCS codes. CMS and the DME MACs provide a list of the specified codes, which is periodically updated. The required Face-to-Face Encounter and Written Order Prior to Delivery List is available [here](https://www.cms.gov/Research-Statistics-Data-and-Systems/Monitoring-Programs/Medicare-FFS-Compliance-Programs/Medical-Review/FacetoFaceEncounterRequirementforCertainDurableMedicalEquipment).

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶47

> Revision Effective Date: 02/28/2022
REQUIREMENTS FOR SPECIFIC DMEPOS ITEMS PURSUANT TO FINAL RULE 1713 (84 FED. REG VOL 217):
Revised: "provides" to "provide"
Removed: "The link will be located here once it is available."
Added: "The required Face-to-Face Encounter and Written Order Prior to Delivery List is available here." with a hyperlink to the list

— `A52464` §Revision History Information ¶157

> A Standard Written Order (SWO) must be communicated to the supplier before a claim is submitted. If the supplier bills for an item addressed in this policy without first receiving a completed SWO, the claim shall be denied as not reasonable and necessary.

— `L33822` §Coverage Guidance ¶83

### c3 (**must**)

The medical record must document that coverage criteria are met

> The CG modifier must be added to the claim line for an adjunctive CGM (E2102) incorporated into an insulin infusion pump and supply allowance (code A4238) only if all of the initial CGM coverage criteria (1)-(5) in the Glucose Monitors LCD and the coverage criteria for an insulin infusion pump as outlined in the External Infusion Pumps LCD (L33794) are met. For continued coverage of adjunctive CGM devices incorporated into an insulin infusion pump (code E2102) and the supply allowance (code A4238), the CG modifier must be added to the claim line only if the continued coverage criteria in the G […]

— `A52464` §MODIFIERS ¶70

> For initial coverage of non-adjunctive CGM devices (code E2103) and the supply allowance (code A4239) the CG modifier must be added to the claim line only if all of the CGM coverage criteria (1)-(5) in the Glucose Monitors LCD are met. For continued coverage of non-adjunctive CGM devices (code E2103) and the supply allowance (code A4239) the CG modifier must be added to the claim line only if the continued coverage criterion in the Glucose Monitors LCD is met. If any of the coverage criteria are not met, the CG modifier must not be used.

— `A52464` §MODIFIERS ¶69

> For criterion 4B, the treating practitioner's medical record must document the beneficiary has a history of problematic hypoglycemia consistent with one of the following pathways to coverage:

— `A52464` §POLICY SPECIFIC DOCUMENTATION REQUIREMENTS ¶58

## Required evidence key phrases

### e1 (**must**) — L33822 [LCD]

`treating practitioner`

> The treating practitioner has had an in-person or Medicare-approved telehealth visit to evaluate the beneficiary's diabetes control; and,

— `A52464` §POLICY SPECIFIC DOCUMENTATION REQUIREMENTS ¶54

> For criterion 4B, the treating practitioner's medical record must document the beneficiary has a history of problematic hypoglycemia consistent with one of the following pathways to coverage:

— `A52464` §POLICY SPECIFIC DOCUMENTATION REQUIREMENTS ¶58

> For the in-person or Medicare-approved telehealth treating practitioner visit that is required as part of the ongoing provision of a CGM, there must be sufficient information in the beneficiary's medical record to determine that the beneficiary continues to adhere to their diabetes treatment regimen and use of the CGM device.

— `A52464` §POLICY SPECIFIC DOCUMENTATION REQUIREMENTS ¶59

### e2 (optional) — A52464 [Article]

`standard written order`

> Final Rule 1713 (84 Fed. Reg Vol 217) requires a face-to-face encounter and a Written Order Prior to Delivery (WOPD) for specified HCPCS codes. CMS and the DME MACs provide a list of the specified codes, which is periodically updated. The required Face-to-Face Encounter and Written Order Prior to Delivery List is available [here](https://www.cms.gov/Research-Statistics-Data-and-Systems/Monitoring-Programs/Medicare-FFS-Compliance-Programs/Medical-Review/FacetoFaceEncounterRequirementforCertainDurableMedicalEquipment).

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶47

> A Standard Written Order (SWO) must be communicated to the supplier before a claim is submitted. If the supplier bills for an item addressed in this policy without first receiving a completed SWO, the claim shall be denied as not reasonable and necessary.

— `L33822` §Coverage Guidance ¶83

> r CGM systems RELATED LOCAL COVERAGE DOCUMENTS: Added: LCD-related Standard Documentation Requirements Language Article |
| 10/01/2016 | R3 | Revision Effective Date: 07/01/2016 NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES: Revised Standard Language to add Statutory Prescription (Order) Requirements, revised Face to Face and ACA requirements (Effective 04/28/2016) |
| 07/01/2016 | R2 | Effective July 1, 2016 oversight for DME MAC Articles is the responsibility of CGS Administrators, LLC 18003 and 17013 and Noridian Healthcare Solutions, LLC 19003 and 16013. No other changes have been made […]

— `A52464` §Revision History Information ¶140
