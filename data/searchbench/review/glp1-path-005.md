# glp1-path-005 — validation worksheet

**What Medicare coverage pathway for GLP-1s used for obesity was announced in late 2025, and when does it take effect?**

`glp1` · tier 3 · coverage_pathway · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "BALANCE covers GLP-1s for weight loss in Medicare Part D starting January 2027" — verify by hand
- [forbidden] f2 could not be checked automatically (no quoted wording or code to match): "Part D plans now cover GLP-1s for obesity as a standard Part D benefit" — verify by hand

## Draft summary

CMS announced the BALANCE Model, a voluntary CMS Innovation Center model under which state Medicaid agencies and Medicare Part D plans can cover GLP-1s for weight management; it launches in Medicaid as early as May 2026. Medicare Part D beneficiaries get access instead through the Medicare GLP-1 Bridge, a short-term demonstration operating outside the Part D benefit that provides certain GLP-1s for $50 a month from July 1, 2026, with prior authorization and clinical criteria. The original announcement put BALANCE in Part D in January 2027; CMS now says BALANCE is not launching in Medicare in 2027 and has extended the Bridge through December 31, 2027.

## Governing documents

- `https://www.cms.gov/newsroom/press-releases/cms-launches-voluntary-model-expand-access-life-changing-medicines-promote-healthier-living` via **url** — [CMS Launches Voluntary Model to Expand Access to Life-Changing ...](https://www.cms.gov/newsroom/press-releases/cms-launches-voluntary-model-expand-access-life-changing-medicines-promote-healthier-living) · official_secondary · no date found · 32 paragraphs
- `https://www.cms.gov/priorities/innovation/innovation-models/balance` via **url** — [BALANCE (Better Approaches to Lifestyle and Nutrition ...](https://www.cms.gov/priorities/innovation/innovation-models/balance) · official_secondary · no date found · 112 paragraphs
- `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` via **url** — [Information for Providers - CMS](https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers) · official_secondary · 2026-04-06 · 133 paragraphs
- `https://www.cms.gov/newsroom/press-releases/coming-soon-cms-provide-50-monthly-access-glp-1-medications-medicare-beneficiaries` via **url** — [Coming Soon: CMS to Provide $50 Monthly Access to GLP-1 ...](https://www.cms.gov/newsroom/press-releases/coming-soon-cms-provide-50-monthly-access-glp-1-medications-medicare-beneficiaries) · official_secondary · no date found · 28 paragraphs

## Required claims, against the live text

### c1 (**must**)

CMS announced the BALANCE Model, a voluntary CMS Innovation Center model that lets state Medicaid agencies and Medicare Part D plans cover GLP-1s for weight management

> Participation in BALANCE is voluntary for manufacturers, state Medicaid agencies, and Part D plans. Who can take part:

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §Participant Information ¶81

> The Centers for Medicare & Medicaid Services (CMS) announced today a new voluntary test of a model that is designed to enable Medicare Part D plans and state Medicaid agencies to cover GLP-1 medications used for weight management and metabolic health improvement, while helping control costs for patients and taxpayers.

— `https://www.cms.gov/newsroom/press-releases/cms-launches-voluntary-model-expand-access-life-changing-medicines-promote-healthier-living` §CMS Launches Voluntary Model to Expand Access to Life-Changing Medicines, Promote Healthier Living ¶8

> As part of this voluntary model, CMS will negotiate drug pricing and coverage terms with manufacturers of GLP-1 medications on behalf of state Medicaid agencies and Medicare Part D plan sponsors.

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §BALANCE (Better Approaches to Lifestyle and Nutrition for Comprehensive hEalth) Model ¶67

### c2 (**must**)

BALANCE launches in Medicaid as early as May 2026

> The coverage for weight loss under the BALANCE Model will launch in Medicaid as early as May 2026.

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §When will GLP-1s for weight loss be available under BALANCE? ¶84

> Participation will be voluntary for manufacturers, states, and plans. Additional information will be released in early 2026 regarding state and Part D plan participation. The BALANCE Model will launch in Medicaid as early as May 2026 and in Medicare Part D in January 2027.

— `https://www.cms.gov/newsroom/press-releases/cms-launches-voluntary-model-expand-access-life-changing-medicines-promote-healthier-living` §CMS Launches Voluntary Model to Expand Access to Life-Changing Medicines, Promote Healthier Living ¶13

> ### What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge?

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge? ¶72

### c3 (**must**)

Medicare Part D beneficiaries get access through a separate short-term demonstration, the Medicare GLP-1 Bridge, at $50 per month beginning July 1, 2026

> Eligible Medicare Part D beneficiaries are expected to have access to GLP-1s by July 2026 through a separate short-term demonstration, the Medicare GLP-1 Bridge.

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §When will GLP-1s for weight loss be available under BALANCE? ¶85

> The Medicare GLP-1 Bridge is a short-term demonstration run by CMS that will provide eligible Medicare Part D beneficiaries with access to certain GLP-1 drugs between July 1, 2026, and December 31, 2027.

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the Medicare GLP-1 Bridge? ¶70

> State Medicaid agencies can apply to participate in the model through the [State Request for Applications](/priorities/innovation/files/balance-state-medicaid-rfa.pdf). State Medicaid agencies can join the model beginning in May 2026 through January 1, 2027. CMS will provide eligible Medicare Part D beneficiaries with access to certain GLP-1 drugs through the [Medicare GLP-1 Bridge](https://www.medicare.gov/coverage/weight-loss-drugs) from July 1, 2026, to December 31, 2027.

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §BALANCE (Better Approaches to Lifestyle and Nutrition for Comprehensive hEalth) Model ¶68

### c4 (**must**)

BALANCE is not launching in Medicare Part D in 2027 (the original announcement said January 2027), and the Medicare GLP-1 Bridge is extended through December 31, 2027

> The Medicare GLP-1 Bridge will be extended through December 31, 2027, providing eligible Medicare Part D beneficiaries with access to certain GLP-1 drugs and allowing CMS to collect additional data on GLP-1 utilization to share with Part D plan sponsors ahead of potential implementation of BALANCE in Part D.

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge? ¶73

> ### What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge?

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge? ¶72

> **What is the impact of the BALANCE Model not launching in Medicare in 2027 on the Medicare GLP-1 Bridge?**

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §Will the Medicare GLP-1 Bridge continue into 2027? ¶95

### c5 (optional)

Bridge eligibility requires Part D enrollment in an eligible plan type, use solely to reduce excess body weight or maintain weight reduction, and a prescriber prior authorization attesting to clinical criteria; beneficiaries with type 2 diabetes, moderate-to-severe obstructive sleep apnea or MASH get GLP-1s through their Part D plan instead

> The Medicare GLP-1 Bridge was designed to increase access to GLP-1s for beneficiaries who seek the drug solely to reduce excess body weight or maintain weight reduction. Type 2 diabetes, moderate to severe obstructive sleep apnea, and noncirrhotic metabolic dysfunction-associated steatohepatitis (MASH) indications are eligible for Part D coverage. Beneficiaries with these diagnoses are eligible to receive GLP-1s through their Part D plan and therefore are ineligible to receive them through the Medicare GLP-1 Bridge, even if they otherwise meet the Medicare GLP-1 Bridge clinical criteria. Eligi […]

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What clinical criteria must a beneficiary meet in order to qualify for the Medicare GLP-1 Bridge? ¶84

> The Medicare GLP-1 Bridge was designed to increase access to GLP-1s for beneficiaries who seek the drug solely to reduce excess body weight or maintain weight reduction. Type 2 diabetes, moderate to severe obstructive sleep apnea, and noncirrhotic metabolic dysfunction-associated steatohepatitis (MASH) indications are eligible for Part D coverage. Beneficiaries with these diagnoses are eligible to receive GLP-1s through their Part D plan and therefore are ineligible to receive them through the Medicare GLP-1 Bridge, even if they otherwise meet the Medicare GLP-1 Bridge clinical criteria. Eligi […]

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §Are beneficiaries eligible for the Medicare GLP-1 Bridge if they are prescribed a GLP-1 for a condition other than weight management? ¶97

> Only Medicare Part D beneficiaries who are enrolled in eligible plan types,  use GLP-1s to reduce excess body weight and maintain weight reduction, and meet the Medicare GLP-1 Bridge Clinical Criteria (see FAQ "What clinical criteria must a beneficiary meet in order to qualify for the Medicare GLP-1 Bridge?") will be eligible for coverage under the Medicare GLP-1 Bridge.

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §Are all Medicare beneficiaries able to receive GLP-1 drugs furnished via the Medicare GLP-1 Bridge? ¶79

### c6 (optional)

The Bridge operates outside the Part D benefit's coverage and payment flow, so Part D sponsors carry no risk for drugs furnished under it

> The Medicare GLP-1 Bridge will operate outside of the Medicare Part D benefit's coverage and payment flow. As a result, Part D sponsors will not carry risk for eligible GLP-1 drugs furnished under the Medicare GLP-1 Bridge, and Part D sponsors do not have to opt in to the Medicare GLP-1 Bridge for eligible beneficiaries to access these drugs beginning July 1, 2026. In 2026, CMS will use a single central processor to manage prior authorization, claims adjudication, and payment to pharmacies for the Medicare GLP-1 Bridge.

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the Medicare GLP-1 Bridge? ¶71

> The GLP-1 payment demonstration will operate outside of the Medicare Part D benefit's coverage and payment flow, which means that Part D Plan Sponsors will not carry risk for eligible GLP-1 products furnished under the demonstration. Beneficiaries enrolled in Medicare Part D who meet the negotiated access criteria will have access to these drugs. Under the demonstration eligible Medicare beneficiaries will pay $50 for a month of GLP-1 medications.

— `https://www.cms.gov/newsroom/press-releases/cms-launches-voluntary-model-expand-access-life-changing-medicines-promote-healthier-living` §CMS Launches Voluntary Model to Expand Access to Life-Changing Medicines, Promote Healthier Living ¶18

> Only Medicare Part D beneficiaries who are enrolled in eligible plan types,  use GLP-1s to reduce excess body weight and maintain weight reduction, and meet the Medicare GLP-1 Bridge Clinical Criteria (see FAQ "What clinical criteria must a beneficiary meet in order to qualify for the Medicare GLP-1 Bridge?") will be eligible for coverage under the Medicare GLP-1 Bridge.

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §Are all Medicare beneficiaries able to receive GLP-1 drugs furnished via the Medicare GLP-1 Bridge? ¶79

## Required evidence key phrases

### e1 (**must**) — https://www.cms.gov/newsroom/press-releases/cms-launches-voluntary-model-expand-access-life-changing-medicines-promote-healthier-living [Press release]

`BALANCE Model`

> ### What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge?

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge? ¶72

> The Medicare GLP-1 Bridge will be extended through December 31, 2027, providing eligible Medicare Part D beneficiaries with access to certain GLP-1 drugs and allowing CMS to collect additional data on GLP-1 utilization to share with Part D plan sponsors ahead of potential implementation of BALANCE in Part D.

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge? ¶73

> **What drugs are included in the BALANCE Model?**

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §What drugs are included in the BALANCE Model? ¶91

`launch in Medicaid as early as May 2026`

> The coverage for weight loss under the BALANCE Model will launch in Medicaid as early as May 2026.

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §When will GLP-1s for weight loss be available under BALANCE? ¶84

> Participation will be voluntary for manufacturers, states, and plans. Additional information will be released in early 2026 regarding state and Part D plan participation. The BALANCE Model will launch in Medicaid as early as May 2026 and in Medicare Part D in January 2027.

— `https://www.cms.gov/newsroom/press-releases/cms-launches-voluntary-model-expand-access-life-changing-medicines-promote-healthier-living` §CMS Launches Voluntary Model to Expand Access to Life-Changing Medicines, Promote Healthier Living ¶13

> State Medicaid agencies can apply to participate in the model through the [State Request for Applications](/priorities/innovation/files/balance-state-medicaid-rfa.pdf). State Medicaid agencies can join the model beginning in May 2026 through January 1, 2027. CMS will provide eligible Medicare Part D beneficiaries with access to certain GLP-1 drugs through the [Medicare GLP-1 Bridge](https://www.medicare.gov/coverage/weight-loss-drugs) from July 1, 2026, to December 31, 2027.

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §BALANCE (Better Approaches to Lifestyle and Nutrition for Comprehensive hEalth) Model ¶68

### e2 (**must**) — https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers [Fact sheet]

`BALANCE Model not launching in 2027`

> ### What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge?

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge? ¶72

> The Medicare GLP-1 Bridge will be extended through December 31, 2027, providing eligible Medicare Part D beneficiaries with access to certain GLP-1 drugs and allowing CMS to collect additional data on GLP-1 utilization to share with Part D plan sponsors ahead of potential implementation of BALANCE in Part D.

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge? ¶73

> **What is the impact of the BALANCE Model not launching in Medicare in 2027 on the Medicare GLP-1 Bridge?**

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §Will the Medicare GLP-1 Bridge continue into 2027? ¶95

`December 31, 2027`

> The Medicare GLP-1 Bridge is a short-term demonstration run by CMS that will provide eligible Medicare Part D beneficiaries with access to certain GLP-1 drugs between July 1, 2026, and December 31, 2027.

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the Medicare GLP-1 Bridge? ¶70

> The Medicare GLP-1 Bridge will be extended through December 31, 2027, providing eligible Medicare Part D beneficiaries with access to certain GLP-1 drugs and allowing CMS to collect additional data on GLP-1 utilization to share with Part D plan sponsors ahead of potential implementation of BALANCE in Part D.

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the impact of the BALANCE Model not launching in 2027 on the Medicare GLP-1 Bridge? ¶73

> The Centers for Medicare & Medicaid Services (CMS) will provide eligible Medicare beneficiaries access to certain GLP-1 medications for $50 per month beginning July 1, 2026, through December 31, 2027.

— `https://www.cms.gov/newsroom/press-releases/coming-soon-cms-provide-50-monthly-access-glp-1-medications-medicare-beneficiaries` §Coming Soon: CMS to Provide $50 Monthly Access to GLP-1 Medications for Medicare Beneficiaries ¶8

### e3 (optional) — https://www.cms.gov/newsroom/press-releases/coming-soon-cms-provide-50-monthly-access-glp-1-medications-medicare-beneficiaries [Press release]

`$50 per month beginning July 1, 2026`

> The Centers for Medicare & Medicaid Services (CMS) will provide eligible Medicare beneficiaries access to certain GLP-1 medications for $50 per month beginning July 1, 2026, through December 31, 2027.

— `https://www.cms.gov/newsroom/press-releases/coming-soon-cms-provide-50-monthly-access-glp-1-medications-medicare-beneficiaries` §Coming Soon: CMS to Provide $50 Monthly Access to GLP-1 Medications for Medicare Beneficiaries ¶8

> The Medicare GLP-1 Bridge is a short-term demonstration run by CMS that will provide eligible Medicare Part D beneficiaries with access to certain GLP-1 drugs between July 1, 2026, and December 31, 2027.

— `https://www.cms.gov/medicare/coverage/prescription-drug-coverage/medicare-glp-1-bridge/information-providers` §What is the Medicare GLP-1 Bridge? ¶70

> State Medicaid agencies can apply to participate in the model through the [State Request for Applications](/priorities/innovation/files/balance-state-medicaid-rfa.pdf). State Medicaid agencies can join the model beginning in May 2026 through January 1, 2027. CMS will provide eligible Medicare Part D beneficiaries with access to certain GLP-1 drugs through the [Medicare GLP-1 Bridge](https://www.medicare.gov/coverage/weight-loss-drugs) from July 1, 2026, to December 31, 2027.

— `https://www.cms.gov/priorities/innovation/innovation-models/balance` §BALANCE (Better Approaches to Lifestyle and Nutrition for Comprehensive hEalth) Model ¶68

## Forbidden claims

- **f1**: BALANCE covers GLP-1s for weight loss in Medicare Part D starting January 2027 — _That was the original announcement; CMS's BALANCE and Bridge pages now state BALANCE is not launching in Medicare in 2027 and extend the Bridge through December 31, 2027_
- **f2**: Part D plans now cover GLP-1s for obesity as a standard Part D benefit — _The Bridge is a demonstration that operates outside the Part D benefit's coverage and payment flow; Part D sponsors carry no risk for it_
