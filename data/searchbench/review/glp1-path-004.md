# glp1-path-004 — validation worksheet

**Does Medicare cover tirzepatide (Zepbound) for obstructive sleep apnea?**

`glp1` · tier 3 · coverage_pathway · split `holdout`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [resolution] 'FDA Zepbound label' has no canonical id; best search hit was https://www.accessdata.fda.gov/drugsatfda_docs/label/2024/217806s003lbl.pdf (primary_policy) — confirm this is the governing document
- [resolution] 'CMS 2024 Part D guidance' has no canonical id; best search hit was https://www.cms.gov/newsroom/fact-sheets/cms-releases-2024-projected-medicare-part-d-premium-and-bid-information?B_Premiums_and_Deductibles_2024_Medicare_Part_D_Income-Related_Monthly_Adjustment_Amounts=&cmdf=2024+Medicare+Parts+A+ (official_secondary) — confirm this is the governing document

## Draft summary

Zepbound received FDA approval for moderate-to-severe OSA in adults with obesity in December 2024. Under the 2024 CMS guidance, Part D may cover an anti-obesity medication for a medically accepted indication other than weight loss, which can include OSA; coverage is plan-dependent and typically subject to utilization management.

## Governing documents

- `FDA Zepbound label` via **search** — [ZEPBOUND (tirzepatide) injection, for subcutaneous use](https://www.accessdata.fda.gov/drugsatfda_docs/label/2024/217806s003lbl.pdf) · primary_policy · 2024-03-01 · 1 paragraphs
- `CMS 2024 Part D guidance` via **search** — [CMS Releases 2024 Projected Medicare Part D Premium and Bid Information](https://www.cms.gov/newsroom/fact-sheets/cms-releases-2024-projected-medicare-part-d-premium-and-bid-information?B_Premiums_and_Deductibles_2024_Medicare_Part_D_Income-Related_Monthly_Adjustment_Amounts=&cmdf=2024+Medicare+Parts+A+) · official_secondary · no date found · 95 paragraphs

## Required claims, against the live text

### c1 (**must**)

FDA approved Zepbound for OSA in adults with obesity in December 2024

> abeled to warn of hazardous waste inside the container. • When your sharps disposal container is almost full, you will need to follow your community guidelines for the right way to dispose of your sharps disposal container. There may be state or local laws about how you Reference ID: 5355063 This label may not be the latest approved by FDA. For current labeling information, please visit https://www.fda.gov/drugsatfda should throw away used needles and syringes. For more information about safe sharps disposal, and for specific information about sharps disposal in the state that you live in, go […]

— `FDA Zepbound label` ¶0

> The projected average total Part D beneficiary premium is projected to decrease by 1.8% in 2024, from $56.49 in 2023 to $55.50 in 2024. The average total Part D premium is the sum of the average basic premium and the average supplementa l premium for plans with enhanced coverage and is the most accurate current projection of what people will pay in 2024 for Part D premiums.

— `CMS 2024 Part D guidance` §Lower Average Total Part D Premiums in 2024 ¶31

> Additional enhancements to the Part D program begin in 2025 including a $2,000 out-of-pocket cap for Part D prescription drugs and the option for those with Medicare Part D coverage to pay out-of-pocket costs in monthly amounts spread over the year.

— `CMS 2024 Part D guidance` §Changes Impacting Part D Premiums in 2024 ¶57

### c2 (**must**)

Part D may cover it for the OSA indication under the medically-accepted-indication guidance

> g of your stomach (gastroparesis) or problems with digesting food. • have a history of diabetic retinopathy. • are pregnant or plan to become pregnant. ZEPBOUND may harm your unborn baby. Tell your healthcare provider if you become pregnant while using ZEPBOUND. ◦ Pregnancy Exposure Registry: There will be a pregnancy exposure registry for women who have taken ZEPBOUND during pregnancy. The purpose of this registry is to collect information about the health of you and your baby. Talk to your healthcare provider about how you can take part in this registry or you may contact Eli Lilly and Compa […]

— `FDA Zepbound label` ¶0

> *   The program-wide average total Part D premium is projected to decrease from $56.49 in 2023 to $55.50 in 2024.
*   The final total Part D premiums that beneficiaries will pay for Part D coverage may change and will be announced in September, prior to open enrollment.

— `CMS 2024 Part D guidance` §Average Total Part D Monthly Premium ¶50

> Many Part D plans provide a richer benefit than the basic Part D benefit (for instance, through lower cost-sharing than required under the basic benefit, coverage of certain non-Part D drugs, etc.); such plans are called "enhanced alternative" plans. The supplemental coverage provided by an enhanced alternative plan is paid for with an additional monthly "supplemental premium." Roughly 75% of beneficiaries are enrolled in enhanced plans in 2023.

— `CMS 2024 Part D guidance` §Average Supplemental Part D Premium ¶46

### c3 (optional)

Coverage is plan-dependent

> The projected average total Part D beneficiary premium is projected to decrease by 1.8% in 2024, from $56.49 in 2023 to $55.50 in 2024. The average total Part D premium is the sum of the average basic premium and the average supplementa l premium for plans with enhanced coverage and is the most accurate current projection of what people will pay in 2024 for Part D premiums.

— `CMS 2024 Part D guidance` §Lower Average Total Part D Premiums in 2024 ¶31

> As discussed above, the average total Part D premium is the sum of the average basic premium and the average supplemental premium for plans with enhanced coverage and is the most accurate projection of what people with Part D are likely to pay on average in premiums, before subsidies and the application of MA rebates are considered.

— `CMS 2024 Part D guidance` §Average Total Part D Monthly Premium ¶49

> Many Part D plans provide a richer benefit than the basic Part D benefit (for instance, through lower cost-sharing than required under the basic benefit, coverage of certain non-Part D drugs, etc.); such plans are called "enhanced alternative" plans. The supplemental coverage provided by an enhanced alternative plan is paid for with an additional monthly "supplemental premium." Roughly 75% of beneficiaries are enrolled in enhanced plans in 2023.

— `CMS 2024 Part D guidance` §Average Supplemental Part D Premium ¶46

## Required evidence key phrases

### e1 (**must**) — FDA Zepbound label [Label]

`obstructive sleep apnea`

> omized, double-blind, placebo-controlled trials (Study 1 and Study 2) in adults aged 18 years and older, in which weight reduction was assessed after 72 weeks of treatment (at least 52 weeks at maintenance dose). In Study 1, the dose of ZEPBOUND or matching placebo was escalated to 5 mg, 10 mg, or 15 mg subcutaneously once weekly during a 20-week titration period followed by the maintenance period. In Study 2, the dose of ZEPBOUND or matching placebo was escalated to 10 mg or 15 mg subcutaneously once weekly during a 20-week titration period followed by the maintenance period. In Studies 1 and […]

— `FDA Zepbound label` ¶0
