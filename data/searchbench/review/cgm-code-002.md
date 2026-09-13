# cgm-code-002 — validation worksheet

**How much CGM supply can Medicare cover per month, and how is it billed?**

`cgm` · tier 2 · coding · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Draft summary

Supplies for a non-adjunctive CGM are billed as one unit of A4239 per month (a monthly supply allowance covering sensors and transmitters); quantities beyond the allowance are not separately payable.

## Governing documents

- `A52464` via **record_url** — [Glucose Monitor - Policy Article (A52464) - CMS](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464) · primary_policy · 2025-02-18 · 281 paragraphs

## Required claims, against the live text

### c1 (**must**)

Supplies are billed as a monthly supply allowance (one unit per month)

> A supplier does not have to deliver supplies used with a CGM every month in order to bill code A4238 or A4239 every month. In order to bill code A4238 or A4239, the supplier must have previously delivered quantities of supplies that are sufficient to last for one (1) full month, thirty (30) days, following the DOS on the claim. Suppliers must monitor usage of supplies. Billing for code A4238 or A4239 may continue on a monthly basis as long as sufficient supplies remain to last for one (1) full month, thirty (30) days, as previously described. If there are insufficient supplies to be able to la […]

— `A52464` §CODING GUIDELINES ¶79

> Revision Effective Date: 01/01/2024
CODING GUIDELINES:
Removed: Language regarding billing only one (1) month, thirty (30) days of the supply allowance for code A4238 or A4239
Added: Language regarding billing up to a maximum of three (3) months, ninety (90) days of the supply allowance for code A4238 or A4239

— `A52464` §Revision History Information ¶151

> The supply allowance for supplies used with a CGM system (A4238, A4239) encompasses all items necessary for the use of the device and includes but is not limited to, CGM sensors and transmitters. For non-adjunctive CGMs, the supply allowance (A4239) also includes a home BGM and related supplies (test strips, lancets, lancing device, calibration solution, and batteries), if necessary. Supplies or accessories billed separately will be denied as unbundling.

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶33

### c2 (**must**)

Sensors and transmitters are included in the allowance, not billed separately

> For adjunctive CGMs, the supply allowance (A4238) encompasses all items necessary for the use of the device and includes but is not limited to, CGM sensors and transmitters. Separate billing of CGM sensors and transmitters will be denied as unbundling. Code A4238 does not include a home BGM (HCPCS codes E0607, E2100, E2101, E2104) and related BGM testing supplies (HCPCS codes A4233, A4234, A4235, A4236, A4244, A4245, A4246, A4247, A4250, A4253, A4255, A4256, A4257, A4258, A4259, A4271). These items may be billed separately, in addition to code A4238.

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶34

> The supply allowance for supplies used with a CGM system (A4238, A4239) encompasses all items necessary for the use of the device and includes but is not limited to, CGM sensors and transmitters. For non-adjunctive CGMs, the supply allowance (A4239) also includes a home BGM and related supplies (test strips, lancets, lancing device, calibration solution, and batteries), if necessary. Supplies or accessories billed separately will be denied as unbundling.

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶33

> The CGM supply allowance includes all items necessary for the use of the device and includes, but is not limited to, CGM sensors and transmitters. For non-adjunctive CGMs, the supply allowance (A4239) also includes a home BGM and related supplies (test strips, lancets, lancing device, calibration solution, and batteries), if necessary. Supplies used with a non-covered CGM are considered non-covered (no Medicare benefit) and must not be billed using HCPCS code A4238 or A4239.

— `A52464` §CODING GUIDELINES ¶78

## Required evidence key phrases

### e1 (**must**) — A52464 [Article]

`A4239`

> Nonadjunctive CGM devices coded E2103 and related supplies coded A4239 encompass both devices classified by the FDA as Class III and devices otherwise classified by the FDA. If Class III, then claims for codes E2103 and A4239 must include the KF modifier. If not Class III, then claims for codes E2103 and A4239 must not include the KF modifier. If uncertain whether the specific device is Class III, the supplier should confirm classification with the FDA or manufacturer prior to billing.

— `A52464` §MODIFIERS ¶72

> Revision Effective Date: 01/01/2024
CODING GUIDELINES:
Removed: Language regarding billing only one (1) month, thirty (30) days of the supply allowance for code A4238 or A4239
Added: Language regarding billing up to a maximum of three (3) months, ninety (90) days of the supply allowance for code A4238 or A4239

— `A52464` §Revision History Information ¶151

> The supply allowance for supplies used with a CGM system (A4238, A4239) encompasses all items necessary for the use of the device and includes but is not limited to, CGM sensors and transmitters. For non-adjunctive CGMs, the supply allowance (A4239) also includes a home BGM and related supplies (test strips, lancets, lancing device, calibration solution, and batteries), if necessary. Supplies or accessories billed separately will be denied as unbundling.

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶33

`supply allowance`

> Revision Effective Date: 01/01/2024
CODING GUIDELINES:
Removed: Language regarding billing only one (1) month, thirty (30) days of the supply allowance for code A4238 or A4239
Added: Language regarding billing up to a maximum of three (3) months, ninety (90) days of the supply allowance for code A4238 or A4239

— `A52464` §Revision History Information ¶151

> Up to a maximum of three (3) months, ninety (90) days of the supply allowance may be billed for code A4238 or A4239 to the DME MAC at a time and suppliers may not dispense more than a ninety (90) day supply.

— `A52464` §CODING GUIDELINES ¶80

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
