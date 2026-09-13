# adv-glp1-002 — validation worksheet

**If the FDA approves a GLP-1 for a new indication, does that mean Medicare Part D will cover it for that indication?**

`glp1` · tier 4 · contradiction · split `dev`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [resolution] 'CMS 2024 Part D guidance' has no canonical id; best search hit was https://www.cms.gov/newsroom/fact-sheets/cms-releases-2024-projected-medicare-part-d-premium-and-bid-information?B_Premiums_and_Deductibles_2024_Medicare_Part_D_Income-Related_Monthly_Adjustment_Amounts=&cmdf=2024+Medicare+Parts+A+ (official_secondary) — confirm this is the governing document
- [key_phrase] e1 (CMS 2024 Part D guidance): medically accepted indication not found in the live document [resolved by search - confirm the document before acting]
- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "FDA approval guarantees Medicare coverage" — verify by hand

## Draft summary

Not automatically. FDA approval establishes a labeled indication; Part D coverage requires the drug to be for a medically accepted indication, to be on the plan's formulary or obtained via exception, and not to fall under a statutory exclusion (e.g., weight loss). The 2024 CMS guidance illustrates the distinction.

## Governing documents

- `CMS 2024 Part D guidance` via **search** — [CMS Releases 2024 Projected Medicare Part D Premium and Bid Information](https://www.cms.gov/newsroom/fact-sheets/cms-releases-2024-projected-medicare-part-d-premium-and-bid-information?B_Premiums_and_Deductibles_2024_Medicare_Part_D_Income-Related_Monthly_Adjustment_Amounts=&cmdf=2024+Medicare+Parts+A+) · official_secondary · no date found · 95 paragraphs

## Required claims, against the live text

### c1 (**must**)

FDA approval does not by itself create Part D coverage

> *   Cost-sharing for Part D drugs will be eliminated for beneficiaries in the catastrophic phase of coverage.
*   The LIS, or the Extra Help, program, will be expanded so that beneficiaries who earn between 135% and 150% of the federal poverty level and meet statutory resource limit requirements will receive the full LIS that, prior to 2024, were available only to beneficiaries earning less than 135% of the federal poverty level; these subsidies provide for $0 premiums and low-cost, fixed copayments for covered prescription drugs.
*   Part D plans must not apply the deductible to any Part D co […]

— `CMS 2024 Part D guidance` §Changes Impacting Part D Premiums in 2024 ¶56

> The national base beneficiary premium is the starting point for calculating a plan-specific basic Part D premium. This value is calculated per a statutory formula, using a percentage of bids and estimates of reinsurance costs submitted by certain Part D plans for the statutory minimum level of coverage Part D plans are required to provide (known as the "basic" benefit). Beginning in 2024, the annual increase in the base beneficiary premium is capped by the prescription drug law's premium stabilization provision, not to exceed 6% per year. In 2024, the premium stabilization provision reduced th […]

— `CMS 2024 Part D guidance` §Base Beneficiary Premium ¶41

> Many Part D plans provide a richer benefit than the basic Part D benefit (for instance, through lower cost-sharing than required under the basic benefit, coverage of certain non-Part D drugs, etc.); such plans are called "enhanced alternative" plans. The supplemental coverage provided by an enhanced alternative plan is paid for with an additional monthly "supplemental premium." Roughly 75% of beneficiaries are enrolled in enhanced plans in 2023.

— `CMS 2024 Part D guidance` §Average Supplemental Part D Premium ¶46

### c2 (**must**)

Statutory exclusions and plan formulary/utilization management still apply

> *   Cost-sharing for Part D drugs will be eliminated for beneficiaries in the catastrophic phase of coverage.
*   The LIS, or the Extra Help, program, will be expanded so that beneficiaries who earn between 135% and 150% of the federal poverty level and meet statutory resource limit requirements will receive the full LIS that, prior to 2024, were available only to beneficiaries earning less than 135% of the federal poverty level; these subsidies provide for $0 premiums and low-cost, fixed copayments for covered prescription drugs.
*   Part D plans must not apply the deductible to any Part D co […]

— `CMS 2024 Part D guidance` §Changes Impacting Part D Premiums in 2024 ¶56

> The base beneficiary premium is used to calculate a plan-specific monthly premium for the basic benefit offered by each Part D plan, called the basic Part D premium. Specifically, the plan-specific basic Part D premium is calculated as the sum of the base beneficiary premium and the difference between the plan's monthly bid and the national average monthly bid amount. Thus, the plan-specific basic premium can be higher or lower than the base beneficiary premium, depending on if the plan's bid is higher or lower than the national average monthly bid amount. These plan-specific basic premiums ac […]

— `CMS 2024 Part D guidance` §Average Basic Part D Premium ¶43

> The national base beneficiary premium is the starting point for calculating a plan-specific basic Part D premium. This value is calculated per a statutory formula, using a percentage of bids and estimates of reinsurance costs submitted by certain Part D plans for the statutory minimum level of coverage Part D plans are required to provide (known as the "basic" benefit). Beginning in 2024, the annual increase in the base beneficiary premium is capped by the prescription drug law's premium stabilization provision, not to exceed 6% per year. In 2024, the premium stabilization provision reduced th […]

— `CMS 2024 Part D guidance` §Base Beneficiary Premium ¶41

### c3 (optional)

A medically accepted indication other than weight loss can be covered per 2024 guidance

> *   Cost-sharing for Part D drugs will be eliminated for beneficiaries in the catastrophic phase of coverage.
*   The LIS, or the Extra Help, program, will be expanded so that beneficiaries who earn between 135% and 150% of the federal poverty level and meet statutory resource limit requirements will receive the full LIS that, prior to 2024, were available only to beneficiaries earning less than 135% of the federal poverty level; these subsidies provide for $0 premiums and low-cost, fixed copayments for covered prescription drugs.
*   Part D plans must not apply the deductible to any Part D co […]

— `CMS 2024 Part D guidance` §Changes Impacting Part D Premiums in 2024 ¶56

> Additional information about the IRA and Medicare can be found [here](https://www.cms.gov/priorities/medicare-prescription-drug-affordability/medicare-prescription-drug-affordability).

— `CMS 2024 Part D guidance` §Changes Impacting Part D Premiums in 2024 ¶58

> [2]The IRA's premium stabilization provision caps the increase in the base beneficiary premium, which is the starting point for calculating the plan-specific basic Part D premium. The plan-specific basic premium can be higher or lower than the base beneficiary premium depending on if the plan's bid is higher or lower than the national average bid. Moreover, the base beneficiary premium is calculated across certain plans that submit bids, as specified by statute, while the average basic premium is calculated across all plans that submit bids.

— `CMS 2024 Part D guidance` §Lower Beneficiary Cost-Sharing at the Pharmacy Counter in 2024 ¶66

## Required evidence key phrases

### e1 (**must**) — CMS 2024 Part D guidance [Guidance]

`medically accepted indication`

_no matching passage in the fetched documents._

## Forbidden claims

- **f1**: FDA approval guarantees Medicare coverage — _false_
