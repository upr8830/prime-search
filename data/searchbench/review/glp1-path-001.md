# glp1-path-001 — validation worksheet

**Does Medicare cover semaglutide, and under what circumstances?**

`glp1` · tier 3 · coverage_pathway · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [resolution] 'CMS March 2024 Part D guidance on anti-obesity medications' has no canonical id; best search hit was https://aspe.hhs.gov/sites/default/files/documents/127bd5b3347b34be31ac5c6b5ed30e6a/medicare-coverage-anti-obesity-meds.pdf (official_secondary) — confirm this is the governing document
- [key_phrase] e1 cites 'Section 1927(d)(2)(A)', which is not in governing_documents — add it there or correct the evidence
- [key_phrase] e2 cites 'CMS 2024 Part D guidance', which is not in governing_documents — add it there or correct the evidence

## Draft summary

Medicare Part D plans may cover semaglutide (Ozempic) for type 2 diabetes. Semaglutide for weight loss alone (Wegovy) has been excluded under the Part D statutory exclusion of weight-loss agents; since the March 2024 CMS guidance, Part D may cover Wegovy for a medically accepted indication other than weight loss (cardiovascular risk reduction in adults with established CVD and overweight/obesity). 2025–2026 CMS actions on obesity coverage must be checked for current status and effective dates.

## Governing documents

- `CMS March 2024 Part D guidance on anti-obesity medications` via **search** — [Medicare Coverage of Anti-Obesity Medications | HHS ASPE](https://aspe.hhs.gov/sites/default/files/documents/127bd5b3347b34be31ac5c6b5ed30e6a/medicare-coverage-anti-obesity-meds.pdf) · official_secondary · no date found · 1 paragraphs

## Required claims, against the live text

### c1 (**must**)

Part D may cover semaglutide for type 2 diabetes

> are Coverage Of Anti-Obesity Medicines Could Increase Annual Spending By $3.1 Billion To $6.1 Billion. Health Affairs 43, no. 9 (1254-1262). https://doi.org/10.1377/hlthaff.2024.00356. 13 Congressional Budget Office, How Would Authorizing Medicare to Cover Anti-Obesity Medications Affect the Federal Budget? (October 2024). https://www.cbo.gov/publication/60441. 14 Eli Lilly and Company. (June 2024). Lilly's tirzepatide reduced obstructive sleep apnea (OSA) severity in adults with type 2 diabetes. Retrieved November 21, 2024, from https://investor.lilly.com/news-releases/news-release-details/li […]

— `CMS March 2024 Part D guidance on anti-obesity medications` ¶0

### c2 (**must**)

Weight-loss use alone is excluded under the Part D statute

> g new initiators of GLP-1 receptor agonist treatment Estimate of costs CMS Office of the Actuary (OACT) Expanding access to prescribed AOMs to Medicare enrollees for the treatment of obesity Obesity: 22% 73% Includes type 2 diabetes, cardiovascular disease, and sleep apnea 7% (2022) 10% in the first year, grows by 0.3% annually 52.5% will stop after two months $1.4 billion in first year; $24.8 billion total over a ten-year period. Congressional Budget Office (CBO) Expanding access to AOMs to Medicare enrollees with obesity alone or overweight accompanied with a weight-related condition Obesity […]

— `CMS March 2024 Part D guidance on anti-obesity medications` ¶0

### c3 (**must**)

Since March 2024, Part D may cover Wegovy for cardiovascular risk reduction as a medically accepted indication

> diovascular disease.9 They have demonstrated positive effects on blood pressure and lipid profiles, contributing to their overall cardiovascular benefits.10 Finally, there is evidence that GLP-1 receptor agonists improve sleep apnea, and Eli Lilly has submitted application for approval for this indication to the FDA for Zepbound.11 With the approval of additional GLP-1 receptor agonists for obesity treatment and the proposed reinterpretation to allow Medicare Part D enrollees to gain access to these treatments for weight reduction and management, Medicare enrollees may soon have access to a ne […]

— `CMS March 2024 Part D guidance on anti-obesity medications` ¶0

### c4 (**must**)

Status of 2025–2026 obesity coverage changes is stated with dates

> g new initiators of GLP-1 receptor agonist treatment Estimate of costs CMS Office of the Actuary (OACT) Expanding access to prescribed AOMs to Medicare enrollees for the treatment of obesity Obesity: 22% 73% Includes type 2 diabetes, cardiovascular disease, and sleep apnea 7% (2022) 10% in the first year, grows by 0.3% annually 52.5% will stop after two months $1.4 billion in first year; $24.8 billion total over a ten-year period. Congressional Budget Office (CBO) Expanding access to AOMs to Medicare enrollees with obesity alone or overweight accompanied with a weight-related condition Obesity […]

— `CMS March 2024 Part D guidance on anti-obesity medications` ¶0

## Required evidence key phrases

### e1 (optional) — Section 1927(d)(2)(A) [Statute]

`weight loss`

> are Coverage Of Anti-Obesity Medicines Could Increase Annual Spending By $3.1 Billion To $6.1 Billion. Health Affairs 43, no. 9 (1254-1262). https://doi.org/10.1377/hlthaff.2024.00356. 13 Congressional Budget Office, How Would Authorizing Medicare to Cover Anti-Obesity Medications Affect the Federal Budget? (October 2024). https://www.cbo.gov/publication/60441. 14 Eli Lilly and Company. (June 2024). Lilly's tirzepatide reduced obstructive sleep apnea (OSA) severity in adults with type 2 diabetes. Retrieved November 21, 2024, from https://investor.lilly.com/news-releases/news-release-details/li […]

— `CMS March 2024 Part D guidance on anti-obesity medications` ¶0

### e2 (**must**) — CMS 2024 Part D guidance [Guidance]

`medically accepted indication`

> maglutide X Saxenda liraglutide X Victoza liraglutide X X Wegovy semaglutide X X Zepbound tirzepatide X Notes: BMI=Body Mass Index. *Indications shown selected based on relevance to subject matter. **The indication specifies that the medication is an adjunct to a reduced calorie diet and increased physical activity. It targets patients with obesity or those with overweight with a weight-related comorbid condition. For Wegovy and Zepbound, the indication specifically reads "to reduce excess body weight and maintain weight reduction long term." ***Adjunct to diet and exercise to improve glycemic […]

— `CMS March 2024 Part D guidance on anti-obesity medications` ¶0
