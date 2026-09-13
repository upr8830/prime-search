# cgm-elig-002 — validation worksheet

**How does the Medicare LCD for glucose monitors define 'problematic hypoglycemia'?**

`cgm` · tier 1 · eligibility · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [key_phrase] e1 (L33822): level 2, level 3 not found in the live document

## Draft summary

The LCD defines problematic hypoglycemia as recurrent (more than one) level 2 hypoglycemic events (glucose <54 mg/dL) despite multiple attempts to adjust medication or modify the treatment plan, or a history of one level 3 event (glucose <54 mg/dL requiring third-party assistance).

## Governing documents

- `L33822` via **record_url** — [LCD - Glucose Monitors (L33822) - CMS](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822) · primary_policy · 2024-10-01 · 275 paragraphs

## Required claims, against the live text

### c1 (**must**)

Level 2 hypoglycemia is glucose below 54 mg/dL

> If a glucose monitor (code E2100 or E2101) is provided and basic coverage criteria (1)-(2) plus the additional criteria stated above are not met, it will be denied as not reasonable and necessary.

— `L33822` §Coverage Guidance ¶48

> The beneficiary for whom a CGM is being prescribed, to improve glycemic control, meets at least one of the criteria below:

— `L33822` §Coverage Guidance ¶70

> Basic coverage criteria (1)-(2) listed above for all home glucose monitors and related accessories and supplies are met; and,

— `L33822` §Coverage Guidance ¶59

### c2 (**must**)

Level 3 hypoglycemia is an event requiring third-party assistance for treatment

> For any item to be covered by Medicare, it must 1) be eligible for a defined Medicare benefit category, 2) be reasonable and necessary for the diagnosis or treatment of illness or injury or to improve the functioning of a malformed body member, and 3) meet all other applicable Medicare statutory and regulatory requirements.

— `L33822` §Coverage Guidance ¶33

> A non-adjunctive CGM can be used to make treatment decisions without the need for a stand-alone BGM to confirm testing results. An adjunctive CGM requires the user verify their glucose levels or trends displayed on a CGM with a BGM prior to making treatment decisions. On February 28, 2022, CMS determined that both non-adjunctive and adjunctive CGMs may be classified as DME.

— `L33822` §Coverage Guidance ¶64

> An order renewal is the act of obtaining an order for an additional period of time beyond that previously ordered by the treating practitioner.

— `L33822` §Appendices ¶137

### c3 (**must**)

Recurrent level 2 events or at least one level 3 event qualifies, despite attempts to modify treatment

> The beneficiary for whom a CGM is being prescribed, to improve glycemic control, meets at least one of the criteria below:

— `L33822` §Coverage Guidance ¶70

> The beneficiary has a history of problematic hypoglycemia with documentation of at least one of the following (see the POLICY SPECIFIC DOCUMENTATION REQUIREMENTS section of the LCD-related Policy Article (A52464)):

— `L33822` §Coverage Guidance ¶72

> For any item to be covered by Medicare, it must 1) be eligible for a defined Medicare benefit category, 2) be reasonable and necessary for the diagnosis or treatment of illness or injury or to improve the functioning of a malformed body member, and 3) meet all other applicable Medicare statutory and regulatory requirements.

— `L33822` §Coverage Guidance ¶33

## Required evidence key phrases

### e1 (**must**) — L33822 [LCD]

`level 2`

> In order for CMS to change billing and claims processing systems to accommodate the coverage conditions within the NCD, we instruct contractors and system maintainers to modify the claims processing systems at the national or local level through CR Transmittals. CRs are not policy, rather CRs are used to relay instructions regarding the edits of the various claims processing systems in very descriptive, technical language usually employing the codes or code combinations likely to be encountered with claims subject to the policy in question. As clinical or administrative codes change or system […]

— `L33822` §National Coverage ¶252

> Revision Effective Date: 10/01/2024
HCPCS CODES:
Revised: Long descriptor for HCPCS code A4271 in Group 2 Codes

— `L33822` §Revision History Information ¶145

> Basic coverage criteria (1)-(2) listed above for all home glucose monitors and related accessories and supplies are met; and,

— `L33822` §Coverage Guidance ¶59

`level 3`

> 3) Contact your [MAC](https://www.cms.gov/medicare-coverage-database/reports/local-coverage-mac-contacts-report.aspx?contractType=all&stateRegion=all&contractorName=all&contractorNumber=all).

— `L33822` §Did you receive a Medicare coverage denial? ¶261

> Regardless of utilization, a supplier must not dispense more than a three (3) month quantity of BGM testing supplies at a time.

— `L33822` §Coverage Guidance ¶92

> The supply allowance (code A4238 or A4239) is a monthly allowance that may be billed up to a maximum of three (3) units of service (UOS) per ninety (90) days at a time. Billing more than three (3) UOS per ninety (90) days of code A4238 or A4239 will be denied as not reasonable and necessary. Refer to the CODING GUIDELINES section in the LCD-related Policy Article for additional billing instructions.

— `L33822` §Coverage Guidance ¶78

`third-party`

_no matching passage in the fetched documents._
