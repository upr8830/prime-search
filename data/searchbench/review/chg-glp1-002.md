# chg-glp1-002 — validation worksheet

**Did CMS finalize the November 2024 proposal to allow Medicare Part D coverage of anti-obesity medications?**

`glp1` · tier 3 · change_detection · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [resolution] 'CMS CY2026 MA/Part D final rule' has no canonical id; best search hit was https://www.cms.gov/newsroom/fact-sheets/contract-year-2027-medicare-advantage-part-d-final-rule (official_secondary) — confirm this is the governing document
- [key_phrase] e1 cites 'CY2026 Part D final rule / CMS fact sheet April 2025', which is not in governing_documents — add it there or correct the evidence
- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Medicare began covering obesity drugs under the Nov 2024 rule in 2026" — verify by hand

## Draft summary

No. The November 2024 proposed rule would have reinterpreted the statutory exclusion to permit coverage for obesity; in April 2025 CMS declined to finalize that provision in the CY2026 Part D final rule. Later 2025 actions took a different route (pricing agreements and an Innovation Center model).

## Governing documents

- `CMS CY2026 MA/Part D final rule` via **search** — [Contract Year 2027 Medicare Advantage and Part D Final Rule - CMS](https://www.cms.gov/newsroom/fact-sheets/contract-year-2027-medicare-advantage-part-d-final-rule) · official_secondary · no date found · 36 paragraphs

## Required claims, against the live text

### c1 (**must**)

The November 2024 proposed rule would have permitted Part D coverage for obesity

> # Contract Year 2027 Medicare Advantage and Part D Final Rule

— `CMS CY2026 MA/Part D final rule` §Contract Year 2027 Medicare Advantage and Part D Final Rule ¶5

> On April 2, 2026, the Centers for Medicare & Medicaid Services (CMS) issued a final rule revising the Medicare Advantage (MA) Program, Medicare Prescription Drug Benefit Program (Part D), and Medicare Cost Plan Program. The Contract Year (CY) 2027 MA and Part D final rule aims to improve quality and access to care for people enrolled in these programs by finalizing updates to MA and Part D Star Ratings quality measurements and streamlining certain enrollment processes.

— `CMS CY2026 MA/Part D final rule` §Background ¶9

> Share

— `CMS CY2026 MA/Part D final rule` §Contract Year 2027 Medicare Advantage and Part D Final Rule ¶6

### c2 (**must**)

CMS did not finalize the provision in the April 2025 final rule

> In the proposed rule CMS included a number of requests for information pertaining to a variety of topics ranging from future directions for the MA program, modernizing marketing oversight and agent/broker regulations, the significant growth in dually eligible individual enrollment in chronic condition special needs plans, supporting well-being and nutrition policy in MA, and opportunities to streamline Medicare regulations. While CMS does not respond to specific comments in the final regulation, feedback will be considered for future rulemaking.

— `CMS CY2026 MA/Part D final rule` §Requests for Information ¶23

> On April 2, 2026, the Centers for Medicare & Medicaid Services (CMS) issued a final rule revising the Medicare Advantage (MA) Program, Medicare Prescription Drug Benefit Program (Part D), and Medicare Cost Plan Program. The Contract Year (CY) 2027 MA and Part D final rule aims to improve quality and access to care for people enrolled in these programs by finalizing updates to MA and Part D Star Ratings quality measurements and streamlining certain enrollment processes.

— `CMS CY2026 MA/Part D final rule` §Background ¶9

> # Contract Year 2027 Medicare Advantage and Part D Final Rule

— `CMS CY2026 MA/Part D final rule` §Contract Year 2027 Medicare Advantage and Part D Final Rule ¶5

### c3 (optional)

Subsequent 2025 actions used a different mechanism

> CMS is finalizing two supplemental benefit policies that were proposed in the CY 2026 rule: (1) strengthening SSBCI administration by clarifying eligibility requirements, and increasing transparency by requiring plans to publicly post their plan-developed SSBCI eligibility criteria; and (2) codifying and clarifying requirements for administering supplemental benefits through debit cards, including that debit cards be electronically linked to plan-covered items and services through a real-time identification mechanism to verify eligibility of plan-covered benefits (products) at the point of sal […]

— `CMS CY2026 MA/Part D final rule` §Implementing Certain Provisions of the Inflation Reduction Act (IRA) of 2022 ¶19

> The IRA of 2022 made major changes to the Medicare Part D prescription drug benefit and directed CMS to implement these changes through 2026 via program instructions. With this program instruction authority expiring, CMS is codifying these changes for 2027 and beyond, including eliminating the coverage gap phase, establishing a reduced annual out-of-pocket threshold, removing cost sharing for enrollees in the catastrophic phase, and incorporating the Manufacturer Discount Program that replaced the Coverage Gap Discount Program on January 1, 2025. CMS is also codifying additional operational ch […]

— `CMS CY2026 MA/Part D final rule` §Implementing Certain Provisions of the Inflation Reduction Act (IRA) of 2022 ¶15

> In the proposed rule CMS included a number of requests for information pertaining to a variety of topics ranging from future directions for the MA program, modernizing marketing oversight and agent/broker regulations, the significant growth in dually eligible individual enrollment in chronic condition special needs plans, supporting well-being and nutrition policy in MA, and opportunities to streamline Medicare regulations. While CMS does not respond to specific comments in the final regulation, feedback will be considered for future rulemaking.

— `CMS CY2026 MA/Part D final rule` §Requests for Information ¶23

## Required evidence key phrases

### e1 (**must**) — CY2026 Part D final rule / CMS fact sheet April 2025 [Fact sheet]

`anti-obesity`

_no matching passage in the fetched documents._

## Forbidden claims

- **f1**: Medicare began covering obesity drugs under the Nov 2024 rule in 2026 — _provision not finalized_
