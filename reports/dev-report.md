# SearchBench dev report

Generated 2026-09-13 17:47 UTC by `uv run python -m eval.report --split dev` from the local bench files listed below.

> The dev split is a build-time check: n = 5 questions per configuration, and several metrics rest on a single record. Not a result to quote.

## Configurations

- **baseline-none-deep** — n = 5; uncached (raw TavilySearch, by construction)
  - [baseline-none-dev-20260913-1649-45ba5ed8](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=2de02a0d-e7b2-4e77-b66e-35b8b334ff02) — git `c499974`, evaluator `moonshotai/Kimi-K2.6`, dataset `2b33b5a37f34`, file `reports/bench/baseline-none-dev-20260913-1649-45ba5ed8.json`, rescored 2026-09-13T17:46:57.526357+00:00
- **prime-base-deep** — n = 5; Tavily cache on
  - [prime-base-dev-20260913-1649-5273555d](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=4b381e35-dfce-4f8e-a65c-e3e69b14e84b) — git `c499974`, evaluator `moonshotai/Kimi-K2.6`, dataset `2b33b5a37f34`, file `reports/bench/prime-base-dev-20260913-1649-5273555d.json`, rescored 2026-09-13T17:42:51.672197+00:00

## Coverage

All 12 metric keys populated: yes — baseline-none-deep ✓; prime-base-deep ✓

## Headline

| config | n | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency | contradiction_handling | scope_handling | primary_source_ratio | search_cost | latency_s | tokens | search_efficiency | composite | judge errors | failed runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline-none-deep | 5 | 0.87 | 0.00 | 0.00 | 0.09 | 0.20 | 1.00 | 1.00 | 0.25 | 1 | 11.6 | 8,668 | 8.68 | 0.50 | 0 | 0 |
| prime-base-deep | 5 | 0.68 | 0.62 | 0.60 | 0.97 | 0.97 | 1.00 | 1.00 | 0.78 | 26 | 158.7 | 441,670 | 0.29 | 0.68 | 0 | 0 |

## PRD targets (docs/00 §9)

| config | metric | subset | value | n | target | met |
|---|---|---|---|---|---|---|
| baseline-none-deep | contradiction_handling | tier 4 with expected contradictions | 1.00 | 1 | 0.60 | yes |
| baseline-none-deep | currency | change-detection questions | 1.00 | 1 | 0.80 | yes |
| baseline-none-deep | evidence_recall | all | 0.00 | 4 | 0.75 | no |
| baseline-none-deep | citation_correctness | all | 0.00 | 5 | 0.85 | no |
| prime-base-deep | contradiction_handling | tier 4 with expected contradictions | 1.00 | 1 | 0.60 | yes |
| prime-base-deep | currency | change-detection questions | 0.83 | 1 | 0.80 | yes |
| prime-base-deep | evidence_recall | all | 0.62 | 4 | 0.75 | no |
| prime-base-deep | citation_correctness | all | 0.60 | 5 | 0.85 | no |
| prime-base-deep | answer_correctness | delta over baseline | -0.19 | 5 | 0.25 | no |

## Per tier

| tier | config | n | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency | composite |
|---|---|---|---|---|---|---|---|---|
| 1 | baseline-none-deep | 1 | 1.00 | 0.00 | 0.00 | 0.24 | 0.00 | 0.50 |
| 2 | baseline-none-deep | 1 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.50 |
| 3 | baseline-none-deep | 1 | 0.50 | 0.00 | 0.00 | 0.20 | 1.00 | 0.35 |
| 4 | baseline-none-deep | 2 | 0.92 | 0.00 | 0.00 | 0.00 | 0.00 | 0.57 |
| 1 | prime-base-deep | 1 | 0.50 | 1.00 | 0.62 | 1.00 | 1.00 | 0.66 |
| 2 | prime-base-deep | 1 | 0.32 | 0.50 | 0.62 | 0.83 | 1.00 | 0.46 |
| 3 | prime-base-deep | 1 | 1.00 | 1.00 | 0.62 | 1.00 | 0.83 | 0.89 |
| 4 | prime-base-deep | 2 | 0.79 | 0.00 | 0.56 | 1.00 | 1.00 | 0.71 |

## Per domain

| domain | config | n | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency | composite |
|---|---|---|---|---|---|---|---|---|
| cgm | baseline-none-deep | 2 | 0.75 | 0.00 | 0.00 | 0.22 | 0.50 | 0.42 |
| glp1 | baseline-none-deep | 2 | 0.92 | 0.00 | 0.00 | 0.00 | 0.00 | 0.47 |
| other | baseline-none-deep | 1 | 1.00 | — | 0.00 | 0.00 | 0.00 | 0.70 |
| cgm | prime-base-deep | 2 | 0.75 | 1.00 | 0.62 | 1.00 | 0.92 | 0.77 |
| glp1 | prime-base-deep | 2 | 0.45 | 0.25 | 0.56 | 0.92 | 1.00 | 0.47 |
| other | prime-base-deep | 1 | 1.00 | — | 0.62 | 1.00 | 1.00 | 0.92 |

## Per question

| question | config | composite | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency | status | trace |
|---|---|---|---|---|---|---|---|---|---|
| adv-glp1-002 | baseline-none-deep | 0.44 | 0.84 | 0.00 | 0.00 | 0.00 | 0.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bad-f3b6-79b2-b661-8671f5a9f4d7/run/01a09bad-f3b6-79b2-b661-8671f5a9f4d7?start_time=2026-09-13T16%3A51%3A03.734673%2B00%3A00) |
| adv-glp1-002 | prime-base-deep | 0.49 | 0.58 | 0.00 | 0.50 | 1.00 | 1.00 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bb0-f9b4-7401-89d0-f5a23e97faae/run/01a09bb0-f9b4-7401-89d0-f5a23e97faae?start_time=2026-09-13T16%3A54%3A21.876121%2B00%3A00) |
| cgm-elig-004 | baseline-none-deep | 0.50 | 1.00 | 0.00 | 0.00 | 0.24 | 0.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bb0-4e06-7e80-bddd-69f1d16cd6a4/run/01a09bb0-4e06-7e80-bddd-69f1d16cd6a4?start_time=2026-09-13T16%3A53%3A37.926919%2B00%3A00) |
| cgm-elig-004 | prime-base-deep | 0.66 | 0.50 | 1.00 | 0.62 | 1.00 | 1.00 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bba-cf9f-7351-9142-85733cf6f5de/run/01a09bba-cf9f-7351-9142-85733cf6f5de?start_time=2026-09-13T17%3A05%3A06.463205%2B00%3A00) |
| chg-cgm-002 | baseline-none-deep | 0.35 | 0.50 | 0.00 | 0.00 | 0.20 | 1.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bb0-771c-7630-ab03-92ac8bb05bf8/run/01a09bb0-771c-7630-ab03-92ac8bb05bf8?start_time=2026-09-13T16%3A53%3A48.444661%2B00%3A00) |
| chg-cgm-002 | prime-base-deep | 0.89 | 1.00 | 1.00 | 0.62 | 1.00 | 0.83 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bbf-bf9b-7902-a89e-11bc3a52bdc9/run/01a09bbf-bf9b-7902-a89e-11bc3a52bdc9?start_time=2026-09-13T17%3A10%3A30.043355%2B00%3A00) |
| glp1-path-002 | baseline-none-deep | 0.50 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bac-4226-7e93-b51e-81f295356c4a/run/01a09bac-4226-7e93-b51e-81f295356c4a?start_time=2026-09-13T16%3A49%3A12.742827%2B00%3A00) |
| glp1-path-002 | prime-base-deep | 0.46 | 0.32 | 0.50 | 0.62 | 0.83 | 1.00 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bac-326d-7182-8177-adf2cdaf3910/run/01a09bac-326d-7182-8177-adf2cdaf3910?start_time=2026-09-13T16%3A49%3A08.717752%2B00%3A00) |
| oos-003 | baseline-none-deep | 0.70 | 1.00 | — | 0.00 | 0.00 | 0.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09baf-06df-7a91-878b-a0f395d33490/run/01a09baf-06df-7a91-878b-a0f395d33490?start_time=2026-09-13T16%3A52%3A14.175327%2B00%3A00) |
| oos-003 | prime-base-deep | 0.92 | 1.00 | — | 0.62 | 1.00 | 1.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bb6-7428-7de0-9bce-d00d6ab25995/run/01a09bb6-7428-7de0-9bce-d00d6ab25995?start_time=2026-09-13T17%3A00%3A20.904320%2B00%3A00) |

## Worked examples

### Easy: `cgm-elig-004` (tier 1, eligibility)

**Question.** Does Medicare cover a CGM for a type 1 diabetic using an insulin pump?

**Answer key.** Yes. A beneficiary with diabetes treated with insulin (including via pump) meets the treatment criterion of LCD L33822; the visit and documentation requirements still apply.

| config | composite | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency |
|---|---|---|---|---|---|---|
| baseline-none-deep | 0.50 | 1.00 | 0.00 | 0.00 | 0.24 | 0.00 |
| prime-base-deep | 0.66 | 0.50 | 1.00 | 0.62 | 1.00 | 1.00 |

**baseline-none-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bb0-4e06-7e80-bddd-69f1d16cd6a4/run/01a09bb0-4e06-7e80-bddd-69f1d16cd6a4?start_time=2026-09-13T16%3A53%3A37.926919%2B00%3A00))

> Yes. Medicare covers continuous glucose monitors (CGMs) for people with type 1 diabetes who use insulin pumps, as long as the specific coverage criteria are met.
>
> **Key requirements for coverage:**
>
> - **Diagnosis and treatment:** You must have a diabetes diagnosis and be treated with insulin (any type or regimen) and/or have a documented history of problematic hypoglycemia.
> - **Display device:** Medicare requires the CGM to be used with either a **stand-alone CGM receiver** or an **insulin infusion pump** that is classified as durable medical equipment (DME) to display glucose data. Smartphones/watches can be used in conjunction, but a DME receiver or pump must be used at least some of the time for the supplies to be covered.
> - **Prescription and visit:** Your doctor must prescribe the CGM, document that you or your caregiver has received training, and have an in-person or Medicare-approved telehealth visit with you within 6 months before ordering it.
> - **Approved device:** The CGM must be FDA approved and obtained from a Medicare-approved supplier.
>
> **Insurance structure:**
> - CGMs are covered under **Medicare Part B** as DME, which means you are generally responsible for a 20% copayment after meeting your deductible.
> - You do not have to use insulin four times a day to qualify; since April 2023, use of any insulin qualifies.
>
> **Sources:**
> - AAFP: Medicare Coverage of Continuous Glucose Monitoring ([aafp.org](https://www.aafp.org/fpm/2024/0100/continuous-glucose-monitoring))
> - Breakthrough T1D: Medicare Coverage of Continuous Glucose Monitors ([breakthrought1d.org](https://www.breakthrought1d.org/t1d-resources/insurance/medicare))
> - AARP: Does Medicare Cover Continuous Glucose Monitors? ([aarp.org](https://www.aarp.org/medicare/does-medicare-cover-continuous-glucose-monitors))
> - CMS Policy Article on CGM Coverage ([cms.gov](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleId=52464))

**prime-base-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bba-cf9f-7351-9142-85733cf6f5de/run/01a09bba-cf9f-7351-9142-85733cf6f5de?start_time=2026-09-13T17%3A05%3A06.463205%2B00%3A00))

> ## Answer
> Yes. Under the current Medicare LCD L33822 (effective 2024‑10‑01), a beneficiary with type 1 diabetes who uses an insulin pump meets the coverage criteria for a continuous glucose monitor because insulin‑pump use qualifies as “insulin‑treated,” which is one of the alternatives for initial CGM coverage[15][5][8]. The beneficiary must also satisfy documentation requirements (e.g., testing frequency corroborating supply quantity)[6].
>
> ## Criteria / Details
> - The beneficiary must be **insulin‑treated**; insulin‑pump use satisfies this requirement[15]. 
> - As an alternative to insulin treatment, the beneficiary may qualify with a **history of documented problematic hypoglycemia**[12]. 
> - For supply billing, the beneficiary must be **testing at a frequency that corroborates the quantity of supplies dispensed** (e.g., a log or narrative statement)[6]. 
> - CGM supply allowance codes **A4238 or A4239** may be billed for up to a **maximum 90‑day supply** at a time[10]. 
>

### Contradiction: `adv-glp1-002` (tier 4, contradiction)

**Question.** If the FDA approves a GLP-1 for a new indication, does that mean Medicare Part D will cover it for that indication?

**Answer key.** Not automatically. FDA approval establishes a labeled indication; Part D coverage requires the drug to be for a medically accepted indication, to be on the plan's formulary or obtained via exception, and not to fall under a statutory exclusion (e.g., weight loss). The 2024 CMS guidance illustrates the distinction.

| config | composite | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency |
|---|---|---|---|---|---|---|
| baseline-none-deep | 0.44 | 0.84 | 0.00 | 0.00 | 0.00 | 0.00 |
| prime-base-deep | 0.49 | 0.58 | 0.00 | 0.50 | 1.00 | 1.00 |

**baseline-none-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bad-f3b6-79b2-b661-8671f5a9f4d7/run/01a09bad-f3b6-79b2-b661-8671f5a9f4d7?start_time=2026-09-13T16%3A51%3A03.734673%2B00%3A00))

> I'll search for the relationship between FDA approvals and Medicare Part D coverage determinations for GLP-1s.  No. FDA approval for a new indication is **not sufficient** to guarantee Medicare Part D coverage for that indication. While FDA approval is a necessary prerequisite, Medicare Part D operates on a separate decision-making track.
>
> **Key points:**
>
> - **Distinct lanes:** FDA approval (safety/efficacy) and Medicare coverage are designed to "operate in distinct lanes." CMS and individual Part D plans make coverage decisions independently.
>
> - **Part D formularies are decentralized:** Each Part D sponsor builds its own formulary through an independent Pharmacy & Therapeutics (P&T) committee. Plans decide tier placement, prior authorization requirements, step therapy, and preferred products within CMS guardrails.
>
> - **Indication-specific coverage:** Part D plans may cover a drug for one FDA-approved indication but not another. For example, GLP-1s with weight-loss FDA approvals are generally excluded from Part D coverage when prescribed for weight loss due to a statutory exclusion for drugs used for "weight loss or weight gain," while the same drug may be covered for type 2 diabetes, cardiovascular risk reduction, or sleep apnea if included on the plan’s formulary.
>
> - **Plan-specific rules:** Even for a covered indication, plans can impose utilization management (prior authorization, step therapy, quantity limits) that affects whether a beneficiary can actually access it.
>
> **Bottom line:** FDA approval makes Part D coverage *possible*, but CMS regulations, statutory exclusions, and individual plan formulary determinations ultimately decide if and for which indications a drug is covered.
>
> **Sources:**
> - https://www.americanactionforum.org/insight/white-house-glp-1-coverage-determination-the-end-run-around-cms-regulations
> - https://pmc.ncbi.nlm.nih.gov/articles/PMC12032556
> - https://www.wellcare.com/en/resources/does-medicare-cover-weight-loss-drugs

**prime-base-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bb0-f9b4-7401-89d0-f5a23e97faae/run/01a09bb0-f9b4-7401-89d0-f5a23e97faae?start_time=2026-09-13T16%3A54%3A21.876121%2B00%3A00))

> ## Answer
> FDA approval of a GLP‑1 for a new indication does not automatically mean Medicare Part D will cover it for that indication; coverage depends on whether the indication is for weight management (obesity) or another condition and whether the drug falls under the statutory exclusion for obesity drugs. Weight‑management indications are excluded from basic Part D coverage but may be accessed through the Medicare GLP‑1 Bridge or supplemental plan coverage, whereas indications such as type 2 diabetes, OSA, or MASH are eligible for standard Part D coverage.
>
> ## Criteria / Details
> - Current law prohibits Medicare from covering obesity drugs, creating a statutory exclusion for weight‑loss indications[3]. 
> - Medicare has a statutory exclusion on weight loss drugs[4]. 
> - 42 CFR 423.100 excludes from Part D coverage drugs or medical uses that may be excluded under Medicaid sections 1927(d)(2) or (d)(3)[12]. 
> - Type 2 diabetes, moderate to severe obstructive sleep apnea, and noncirrhotic MASH indications are eligible for Part D coverage and are not eligible for the Medicare GLP‑1 Bridge[7]. 
> - GLP‑1 indications for weight management are not eligible for basic Part D coverage, while the aforementioned indications are eligible[14]. 
> - The Medicare GLP‑1 Bridge operates outside of the Part D benefit’s payment flow, providing access for weight‑management GLP‑1s[2]. 
> - The Bridge was designed for beneficiaries seeking GLP‑1s solely for weight reduction[10]. 
> - Part D plans may offer supplemental coverage for GLP‑1 drugs prescribed for weight management[13]. 
>

### Out of scope: `oos-003` (tier 4, out_of_scope)

**Question.** Does Medicare cover a CGM for a non-diabetic athlete who wants to optimize training?

**Answer key.** No. The LCD requires a diabetes diagnosis; non-diabetic use is not covered. The system should answer briefly and not search for workarounds.

| config | composite | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency |
|---|---|---|---|---|---|---|
| baseline-none-deep | 0.70 | 1.00 | — | 0.00 | 0.00 | 0.00 |
| prime-base-deep | 0.92 | 1.00 | — | 0.62 | 1.00 | 1.00 |

**baseline-none-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09baf-06df-7a91-878b-a0f395d33490/run/01a09baf-06df-7a91-878b-a0f395d33490?start_time=2026-09-13T16%3A52%3A14.175327%2B00%3A00))

> I'll search for current Medicare coverage policies on CGMs for non-diabetic use.  **No — Medicare will not cover a continuous glucose monitor (CGM) for a non-diabetic athlete who wants to optimize training.**
>
> Medicare covers CGMs only under specific medical-necessity criteria:
>
> *   You must have a **diagnosed diabetes mellitus** (type 1 or type 2).
> *   You must either **take insulin** or have a documented history of **Level 2 or Level 3 hypoglycemia** despite treatment adjustments.
> *   The prescribing clinician must have evaluated your diabetes control in an in-person or Medicare-approved telehealth visit within the prior **6 months**.
> *   The device must be **FDA-approved** and acquired from a **Medicare-approved supplier**.
>
> CGMs are classified as durable medical equipment (DME) under Medicare Part B, and coverage is specifically tied to **glycemic control in diabetes management**. Using a CGM for athletic performance, metabolic “biohacking,” or general wellness does not meet Medicare’s coverage requirements.
>
> **Sources:**
> *   [AARP – Does Medicare Cover Continuous Glucose Monitors?](https://www.aarp.org/medicare/does-medicare-cover-continuous-glucose-monitors)
> *   [Medicare.org – Does Medicare Cover Glucose Monitors?](https://www.medicare.org/articles/does-medicare-cover-glucose-monitors)
> *   [Commonwealth Care Alliance – Continuous Glucose Monitors (CGM) Medical Necessity Guideline](https://www.commonwealthcarealliance.org/ma/wp-content/uploads/2024/08/Continuous-Glucose-Monitors-CGM_113_P.08.08.24.pdf)
> *   [BCBSRI Medical Coverage Policy – Glucose Monitoring-Continuous](https://www.bcbsri.com/providers/medicalpolicies/files/glucose-monitoring-continuous)

**prime-base-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09bb6-7428-7de0-9bce-d00d6ab25995/run/01a09bb6-7428-7de0-9bce-d00d6ab25995?start_time=2026-09-13T17%3A00%3A20.904320%2B00%3A00))

> ## Answer
> This asks about coverage for a specific person's situation; the answer below covers only what Medicare policy says about CGM coverage criteria, not a personal coverage decision. 
> Medicare’s coverage for therapeutic continuous glucose monitors (CGMs) requires the beneficiary to have diabetes mellitus, as stated in the Noridian DME policy effective 2026‑04‑01[1] and the CMS LCD L33822 effective 2024‑10‑01[6]. 
> Coverage also requires either insulin treatment or a documented history of problematic hypoglycemia with specific documentation, per the same Noridian policy[2] and the LCD L33822[17]. 
> Because a non‑diabetic athlete does not meet the diabetes mellitus requirement, Medicare does not cover CGM use for training optimization under current policy. 
>
> ## Criteria / Details
> - **Diabetes mellitus required** – “Therapeutic CGM coverage requires the patient to have diabetes mellitus”[1]; “The beneficiary has diabetes mellitus”[6]. 
> - **Insulin‑treated or problematic hypoglycemia pathway** – “The patient is insulin treated, or … has a history of problematic hypoglycemia with documentation”[2]; “Current CGM coverage criterion still requires beneficiary to be insulin‑treated; or,”[17]. 
> - **Supply documentation** – “Following the initial CGM prescription, there must be documentation every six (6) months of an in‑person or Medicare‑approved telehealth visit”[14]. 
> - **Supply billing limit** – “Up to a maximum of three (3) months, ninety (90) days of the supply allowance may be billed for code A4238 or A4239 to the DME MAC at a time”[16] (same limit noted in[11]). 
>

## Cost and latency

| config | search_cost mean | median | latency_s mean | median | tokens mean | median | search_efficiency mean | median | agent tokens total | judge tokens total |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline-none-deep | 1 | 1 | 11.6 | 11.0 | 8,668 | 8,788 | 8.68 | 10.00 | 43,339 | 84,018 |
| prime-base-deep | 26 | 25 | 158.7 | 163.0 | 441,670 | 433,805 | 0.29 | 0.20 | 2,208,352 | 222,637 |

## Evaluator comments

### `adv-glp1-002`

**baseline-none-deep**

- `answer_correctness` 0.84 — claims 4/5 weighted present; missing: c3; summary: consistent
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.00 — 0/12 cited in whole answer (no Criteria / Codes sections); uncited: 'I'll search for the relationship between FDA approvals and Medicare Part D co...'; 'No. FDA approval for a new indication is **not sufficient** to guarantee Medi...'; 'While FDA approval is a necessary prerequisite, Medicare Part D operates on a...'
- `currency` 0.00 — CMS 2024 Part D guidance: not cited; no governing date on record (search-guessed index entry)
- `contradiction_handling` 1.00 — x1 'Label vs coverage': surfaced, governing stated
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.00 — 0/3 citations at official_secondary or better; below: [1] unknown americanactionforum.org, [2] unknown pmc.ncbi.nlm.nih.gov, [3] unknown wellcare.com
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 16.0 — 16.0s wall clock
- `tokens` 8,258 — 7243 in + 1015 out
- `search_efficiency` 8.40 — answer_correctness 0.84 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.58 — claims 3/5 weighted present; missing: c2 (must); summary: partial
- `evidence_recall` 0.00 — unmatched e1 (must) [CMS 2024 Part D guidance: document found, no passage containing 'medically accepted indication'] | search-guessed descriptor (needs_review): e1
- `citation_correctness` 0.50 — 4/8 sampled cited sentences supported (of 8 cited); failing: [7] 'Type 2 diabetes, moderate to severe obstructive sleep apnea, and no...' - The passage specifies noncirrhotic MASH with moderate to advanced liver scarring (fibrosis), not ...; [14] 'GLP‑1 indications for weight management are not eligible for basic ...' - The passage does not state that GLP-1 indications for weight management are ineligible for basic ...; [2] 'The Medicare GLP‑1 Bridge operates outside of the Part D benefit’s ...' - The passage does not specify that the Bridge provides access for weight-management GLP-1s.; [13] 'Part D plans may offer supplemental coverage for GLP‑1 drugs prescr...' - The passage does not mention GLP-1 drugs.
- `citation_completeness` 1.00 — 8/8 cited in Criteria / Details and Codes and documentation
- `currency` 1.00 — CMS 2024 Part D guidance: cited; no governing date on record (search-guessed index entry)
- `contradiction_handling` 1.00 — x1 'Label vs coverage': surfaced, governing stated
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.75 — 6/8 citations at official_secondary or better; below: [3] professional kff.org, [4] professional kff.org
- `search_cost` 35 — 16 searches + 19 fetches
- `latency_s` 201.2 — 201.2s wall clock
- `tokens` 560,665 — 483396 in + 77269 out
- `search_efficiency` 0.17 — answer_correctness 0.58 / max(1, 35 calls) x 10

### `cgm-elig-004`

**baseline-none-deep**

- `answer_correctness` 1.00 — claims 4/4 weighted present; summary: consistent
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.24 — 4/17 cited in whole answer (no Criteria / Codes sections); uncited: 'Yes.'; 'Medicare covers continuous glucose monitors (CGMs) for people with type 1 dia...'; '**Key requirements for coverage:**'
- `currency` 0.00 — L33822: not cited; governing date 2024-10-01 not stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.25 — 1/4 citations at official_secondary or better; below: [1] unknown aafp.org, [2] unknown breakthrought1d.org, [3] unknown aarp.org
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 6.9 — 6.9s wall clock
- `tokens` 8,858 — 7950 in + 908 out
- `search_efficiency` 10.00 — answer_correctness 1.0 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.50 — claims 2/4 weighted present; missing: c2 (must); summary: partial
- `evidence_recall` 1.00 — matched e1 (must) via id (ev_85b3ca6c72)
- `citation_correctness` 0.62 — 5/8 sampled cited sentences supported (of 8 cited); failing: [15][5][8] 'Under the current Medicare LCD L33822 (effective 2024‑10‑01), a ben...' - Passage [15] states that the specific language linking insulin pump use to the insulin-treated cr...; [15] 'The beneficiary must be **insulin‑treated**; insulin‑pump use satis...' - Passage [15] indicates that the mention of insulin pump use was removed from the insulin-treated ...; [12] 'As an alternative to insulin treatment, the beneficiary may qualify...' - Passage [12] describes the problematic hypoglycemia criterion but does not state that it is an al...
- `citation_completeness` 1.00 — 6/6 cited in Criteria / Details and Codes and documentation
- `currency` 1.00 — L33822: cited; governing date 2024-10-01 stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.87 — 13/15 citations at official_secondary or better; below: [3] unknown gohealth.com, [4] unknown usmed.com
- `search_cost` 25 — 12 searches + 13 fetches
- `latency_s` 163.0 — 163.0s wall clock
- `tokens` 458,247 — 400042 in + 58205 out
- `search_efficiency` 0.20 — answer_correctness 0.5 / max(1, 25 calls) x 10

### `chg-cgm-002`

**baseline-none-deep**

- `answer_correctness` 0.50 — claims 2/4 weighted present; missing: c1 (must); summary: partial
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.20 — 2/10 cited in whole answer (no Criteria / Codes sections); uncited: 'I'll search for any recent updates or proposed changes to the Medicare glucos...'; 'Yes, there were two recent finalized revisions to LCD **L33822 (Glucose Monit...'; 'Both were non-discretionary HCPCS code updates issued without a proposed LCD:'
- `currency` 1.00 — L33822: cited; governing date 2024-10-01 stated; order: ordered_with_dates (The answer lists two finalized revisions with specific dates in 2024, ordered chronologically from April to October.)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 1.00 — 2/2 citations at official_secondary or better
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 10.9 — 10.9s wall clock
- `tokens` 8,101 — 7293 in + 808 out
- `search_efficiency` 5.00 — answer_correctness 0.5 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 1.00 — claims 4/4 weighted present; summary: consistent
- `evidence_recall` 1.00 — matched e1 (must) via id (ev_737c6acf9b)
- `citation_correctness` 0.62 — 5/8 sampled cited sentences supported (of 11 cited); failing: [8] 'Policy article A52464 revised effective 02/18/2025 (R19): changed “...' - The passage does not mention version R19.; [9] 'Policy article A52464 revised effective 02/18/2025 (R19): added a n...' - The passage does not mention version R19.; [1][5] 'The reviewer flagged the claim “LCD L33822 has a revision effective...' - The passages do not mention a reviewer or that the claim was flagged as weak.
- `citation_completeness` 1.00 — 8/8 cited in Criteria / Details and Codes and documentation
- `currency` 0.83 — L33822: cited; governing date 2024-10-01 stated; order: dated_not_ordered (The answer lists multiple revisions with specific effective dates (e.g., 10/01/2024, 04/16/2023, 02/18/2025) but pres...)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.89 — 8/9 citations at official_secondary or better; below: [3] unknown journals.sagepub.com
- `search_cost` 24 — 16 searches + 8 fetches
- `latency_s` 146.3 — 146.3s wall clock
- `tokens` 367,754 — 327847 in + 39907 out
- `search_efficiency` 0.42 — answer_correctness 1.0 / max(1, 24 calls) x 10

### `glp1-path-002`

**baseline-none-deep**

- `answer_correctness` 1.00 — claims 5/5 weighted present; summary: consistent
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.00 — 0/19 cited in whole answer (no Criteria / Codes sections); uncited: '**Yes**, Wegovy can be covered under Medicare Part D when prescribed specific...'; 'Here is what you need to know:'; 'In **March 2024**, the FDA expanded Wegovy’s approval to reduce the risk of m...'
- `currency` 0.00 — FDA Wegovy label: not cited; no governing date on record (search-guessed index entry); CMS March 2024 Part D guidance: not cited; no governing date on record (search-guessed index entry)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.00 — 0/6 citations at official_secondary or better; below: [1] unknown medicareinfopro.com, [2] unknown savingadvice.com, [3] unknown coveredusa.org, [4] unknown findhonestcare.com, [5] web novocare.com
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 13.3 — 13.3s wall clock
- `tokens` 8,788 — 7626 in + 1162 out
- `search_efficiency` 10.00 — answer_correctness 1.0 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.32 — claims 2/5 weighted present; missing: c1 (must), c3; summary: inconsistent
- `evidence_recall` 0.50 — matched e1 (must) via host+type (ev_3c75b865ad) | unmatched e2 (must) [CMS 2024 Part D guidance: document found, no passage containing 'medically accepted'] | search-guessed descriptor (needs_review): e1, e2
- `citation_correctness` 0.62 — 5/8 sampled cited sentences supported (of 8 cited); failing: [1][2][4][5][7] '**Conflict:** Sources [1], [2], [4], and [5] indicate Part D covera...' - Source [4] does not mention Wegovy, source [5] does not address Part D coverage, and source [7] d...; [7][4][1][2][5] '**Resolution:** Source [7] is a primary policy document with a late...' - Source [2] has a later revision date (2026-08-28) than source [7] (2026-04-30), and the passages ...; [7] 'Therefore, the exclusion in [7] governs.' - Passage [7] does not state that the exclusion governs or supersedes other coverage.
- `citation_completeness` 0.83 — 5/6 cited in Criteria / Details and Codes and documentation; uncited: 'As a later primary policy document, this exclusion overrides earlier coverage...'
- `currency` 1.00 — FDA Wegovy label: cited; no governing date on record (search-guessed index entry); CMS March 2024 Part D guidance: cited; no governing date on record (search-guessed index entry)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.60 — 3/5 citations at official_secondary or better; below: [1] web healthline.com, [2] web goodrx.com
- `search_cost` 30 — 17 searches + 13 fetches
- `latency_s` 177.7 — 177.7s wall clock
- `tokens` 433,805 — 385130 in + 48675 out
- `search_efficiency` 0.11 — answer_correctness 0.32 / max(1, 30 calls) x 10

### `oos-003`

**baseline-none-deep**

- `answer_correctness` 1.00 — claims 3/3 weighted present; summary: consistent
- `evidence_recall` — — not applicable: the answer key requires no evidence
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.00 — 0/9 cited in whole answer (no Criteria / Codes sections); uncited: 'I'll search for current Medicare coverage policies on CGMs for non-diabetic u...'; 'Medicare covers CGMs only under specific medical-necessity criteria:'; 'You must have a **diagnosed diabetes mellitus** (type 1 or type 2).'
- `currency` 0.00 — L33822: not cited; governing date 2024-10-01 not stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` 1.00 — scope: stated in text; no fabricated payer criteria
- `primary_source_ratio` 0.00 — 0/4 citations at official_secondary or better; below: [1] unknown aarp.org, [2] unknown medicare.org, [3] unknown commonwealthcarealliance.org, [4] unknown bcbsri.com
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 11.0 — 11.0s wall clock
- `tokens` 9,334 — 8530 in + 804 out
- `search_efficiency` 10.00 — answer_correctness 1.0 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 1.00 — claims 3/3 weighted present; summary: consistent
- `evidence_recall` — — not applicable: the answer key requires no evidence
- `citation_correctness` 0.62 — 5/8 sampled cited sentences supported (of 10 cited); failing: [2][17] 'Coverage also requires either insulin treatment or a documented his...' - Passage [17] only mentions insulin treatment and does not mention a history of problematic hypogl...; [2][17] '**Insulin‑treated or problematic hypoglycemia pathway** – “The pati...' - Passage [17] states 'The beneficiary is insulin-treated; or,' which does not match the quoted cla...; [5][12][13][3][4][7][8][15] 'Weak claims (secondary sources or undated documents) such as the AA...' - Passage [3] is a dated revision notice, passages for [4][7][8][15] are absent, and none of the pa...
- `citation_completeness` 1.00 — 6/6 cited in Criteria / Details and Codes and documentation
- `currency` 1.00 — L33822: cited; governing date 2024-10-01 stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` 1.00 — scope: scope_warning field; no fabricated payer criteria
- `primary_source_ratio` 0.80 — 12/15 citations at official_secondary or better; below: [5] unknown aarp.org, [12] web goodrx.com, [13] unknown mddionline.com
- `search_cost` 18 — 8 searches + 10 fetches
- `latency_s` 105.2 — 105.2s wall clock
- `tokens` 387,881 — 341970 in + 45911 out
- `search_efficiency` 0.56 — answer_correctness 1.0 / max(1, 18 calls) x 10
