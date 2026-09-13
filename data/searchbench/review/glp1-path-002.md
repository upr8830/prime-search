# glp1-path-002 — validation worksheet

**Is Wegovy covered under Medicare Part D for cardiovascular risk reduction?**

`glp1` · tier 2 · coverage_pathway · split `dev`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [resolution] 'FDA Wegovy label' has no canonical id; best search hit was https://www.accessdata.fda.gov/drugsatfda_docs/label/2023/215256s007lbl.pdf (primary_policy) — confirm this is the governing document
- [resolution] 'CMS March 2024 Part D guidance' has no canonical id; best search hit was https://www.cms.gov/newsroom/fact-sheets/draft-cy-2025-part-d-redesign-program-instructions-fact-sheet (official_secondary) — confirm this is the governing document
- [key_phrase] e1 (FDA Wegovy label): major adverse cardiovascular events not found in the live document [resolved by search - confirm the document before acting]
- [key_phrase] e2 cites 'CMS 2024 Part D guidance', which is not in governing_documents — add it there or correct the evidence

## Draft summary

Yes, potentially. After the March 2024 FDA label expansion (reduce risk of MACE in adults with established CVD and overweight/obesity), CMS guidance clarified Part D plans may cover anti-obesity medications when used for a medically accepted indication that is not weight loss; plans may apply utilization management.

## Governing documents

- `FDA Wegovy label` via **search** — [[PDF] WEGOVY (semaglutide) injection - accessdata.fda.gov](https://www.accessdata.fda.gov/drugsatfda_docs/label/2023/215256s007lbl.pdf) · primary_policy · 2023-07-01 · 1 paragraphs
- `CMS March 2024 Part D guidance` via **search** — [Draft CY 2025 Part D Redesign Program Instructions Fact Sheet | CMS](https://www.cms.gov/newsroom/fact-sheets/draft-cy-2025-part-d-redesign-program-instructions-fact-sheet) · official_secondary · no date found · 39 paragraphs

## Required claims, against the live text

### c1 (**must**)

FDA expanded the Wegovy label to cardiovascular risk reduction in March 2024

> or repeated measures including treatment as a factor and baseline value as a covariate all nested within visit. 4For patients without type 2 diabetes at randomization (N=129 for WEGOVY-treated patients and N=64 for placebo-treated patients). 5Baseline value is the geometric mean. 14.3 Cardiovascular Outcomes Trial of Semaglutide 0.5 mg and 1 mg in Adult Patients with Type 2 Diabetes and Cardiovascular Disease Semaglutide 0.5 mg and 1 mg (OZEMPIC®) are used in the treatment of type 2 diabetes mellitus in adults. The efficacy of semaglutide at doses of 0.5 mg and 1 mg have not been established f […]

— `FDA Wegovy label` ¶0

> As noted above, CMS will accept comments on the proposals set forth in the Advance Notice through 6:00 PM Eastern Time on Friday March 1, 2024. The 2025 Rate Announcement will be published no later than Monday, April 1, 2024.

— `CMS March 2024 Part D guidance` §To submit comments ¶25

> **To submit comments:**
CMS is voluntarily soliciting comment on the draft program instructions. CMS will accept comments on the Draft CY 2025 Part D Redesign Program Instructions through 6:00 PM Eastern Time on Friday, March 1, 2024, before publishing the Final CY 2025 Part D Redesign Program Instructions no later than April 1, 2024.

— `CMS March 2024 Part D guidance` §To submit comments ¶23

### c2 (**must**)

CMS guidance permits Part D coverage for the CV indication

> he effects on milk production. Semaglutide was present in the milk of lactating rats. When a drug is present in animal milk, it is likely that the drug will be present in human milk (see Data). The developmental and health benefits of breastfeeding should be considered along with the mother's clinical need for WEGOVY and any potential adverse effects on the breastfed infant from WEGOVY or from the underlying maternal condition. Data In lactating rats, semaglutide was detected in milk at levels 3-12 fold lower than in maternal plasma. 8.3 Females and Males of Reproductive Potential Because of t […]

— `FDA Wegovy label` ¶0

> The purpose of the Draft CY 2025 Part D Redesign Program Instructions is to provide interested parties with draft guidance for CY 2025 regarding the implementation of section 11201 of the Inflation Reduction Act of 2022 (IRA) (P.L. 117-169), signed into law on August 16, 2022, which made several amendments and additions to the Social Security Act ("the Act") that affect the structure of the defined standard Part D drug benefit. We invite interested parties to comment on the draft guidance.

— `CMS March 2024 Part D guidance` §Draft CY 2025 Part D Redesign Program Instructions Fact Sheet ¶8

> The draft program instructions contain a detailed description of and guidance related to changes newly in place for CY 2025 made by the IRA, as well as guidance for CY 2023 Medical Loss Ratio (MLR) reporting related to the Inflation Reduction Act Subsidy Amount (IRASA). The draft program instructions are being published concurrently with the CY 2025 Advance Notice that, among other things, announces updates to Part D parameters, some of which are impacted by provisions in the draft program instructions.

— `CMS March 2024 Part D guidance` §Draft CY 2025 Part D Redesign Program Instructions Fact Sheet ¶9

### c3 (optional)

Plans may apply prior authorization or other utilization management

> is label may not be the latest approved by FDA. For current labeling information, please visit https://www.fda.gov/drugsatfda Table 1. BMI Conversion Chart Pediatric Patients Aged 12 Years and Older Select pediatric patients aged 12 years and older for WEGOVY treatment as an adjunct to a reduced calorie diet and increased physical activity for chronic weight management based on the BMI values provided in Tables 1 and 2. Table 1 presents a chart for determining BMI based on height and weight. Table 2 presents BMI cut-offs for obesity in pediatric patients aged 12 years and older, determined bas […]

— `FDA Wegovy label` ¶0

> Section 11201(f) of the IRA directs the Secretary to implement section 11201 of the IRA for 2024, 2025, and 2026 by program instruction or other forms of program guidance, and section 11406(d) of the IRA directs the Secretary to implement section 11406 of the IRA for 2023, 2024, and 2025 by program instruction or other forms of program guidance. In accordance with the law, CMS is issuing these draft program instructions for implementation of section 11201 of the IRA for 2025 and for implementation of MLR reporting instructions related to the IRASA for 2023. In the final program instructions, C […]

— `CMS March 2024 Part D guidance` §To submit comments ¶28

> The 2025 Advance Notice may be viewed by going to: [https://www.cms.gov/Medicare/Health-Plans/MedicareAdvtgSpecRateStats/Announcements-and-Documents](/medicare/payment/medicare-advantage-rates-statistics/announcements-and-documents) and selecting "2025 Advance Notice."

— `CMS March 2024 Part D guidance` §To submit comments ¶27

## Required evidence key phrases

### e1 (**must**) — FDA Wegovy label [Label]

`cardiovascular`

> or repeated measures including treatment as a factor and baseline value as a covariate all nested within visit. 4For patients without type 2 diabetes at randomization (N=129 for WEGOVY-treated patients and N=64 for placebo-treated patients). 5Baseline value is the geometric mean. 14.3 Cardiovascular Outcomes Trial of Semaglutide 0.5 mg and 1 mg in Adult Patients with Type 2 Diabetes and Cardiovascular Disease Semaglutide 0.5 mg and 1 mg (OZEMPIC®) are used in the treatment of type 2 diabetes mellitus in adults. The efficacy of semaglutide at doses of 0.5 mg and 1 mg have not been established f […]

— `FDA Wegovy label` ¶0

`major adverse cardiovascular events`

> or repeated measures including treatment as a factor and baseline value as a covariate all nested within visit. 4For patients without type 2 diabetes at randomization (N=129 for WEGOVY-treated patients and N=64 for placebo-treated patients). 5Baseline value is the geometric mean. 14.3 Cardiovascular Outcomes Trial of Semaglutide 0.5 mg and 1 mg in Adult Patients with Type 2 Diabetes and Cardiovascular Disease Semaglutide 0.5 mg and 1 mg (OZEMPIC®) are used in the treatment of type 2 diabetes mellitus in adults. The efficacy of semaglutide at doses of 0.5 mg and 1 mg have not been established f […]

— `FDA Wegovy label` ¶0

### e2 (**must**) — CMS 2024 Part D guidance [Guidance]

`medically accepted`

_no matching passage in the fetched documents._
