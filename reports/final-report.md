# SearchBench holdout report

Generated 2026-09-14 03:19 UTC by `uv run python -m eval.report --split holdout --passes 2` from the local bench files listed below.

## Configurations

- **baseline-none-deep** — n = 10; uncached (raw TavilySearch, by construction)
  - [baseline-none-holdout-20260914-0227-3acdec9e](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=9c3640fd-6379-48d1-826a-64067c85b6e2) — git `70027ea`, evaluator `moonshotai/Kimi-K2.6`, dataset `2b33b5a37f34`, file `reports/bench/baseline-none-holdout-20260914-0227-3acdec9e.json`
  - [baseline-none-holdout-20260914-0222-5487b5be](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=8a382e68-e6c4-4087-a8c9-25627b52e46d) — git `70027ea`, evaluator `moonshotai/Kimi-K2.6`, dataset `2b33b5a37f34`, file `reports/bench/baseline-none-holdout-20260914-0222-5487b5be.json`
- **prime-base-deep** — n = 10; Tavily cache on
  - [prime-base-holdout-20260914-0250-7ded4cbf](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=5fbbad9a-4a93-476c-9ceb-5078e6613966) — git `da7067f`, evaluator `moonshotai/Kimi-K2.6`, dataset `2b33b5a37f34`, file `reports/bench/prime-base-holdout-20260914-0250-7ded4cbf.json`
  - [prime-base-holdout-20260914-0232-1acb321c](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=74673468-7163-421b-a7c1-10f29b529bc6) — git `da7067f`, evaluator `moonshotai/Kimi-K2.6`, dataset `2b33b5a37f34`, file `reports/bench/prime-base-holdout-20260914-0232-1acb321c.json`

## Coverage

All 12 metric keys populated: yes — baseline-none-deep ✓; prime-base-deep ✓

## Headline

| config | n | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency | contradiction_handling | scope_handling | primary_source_ratio | search_cost | latency_s | tokens | search_efficiency | composite | judge errors | failed runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline-none-deep | 10 | 0.64 ± 0.05 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.18 ± 0.02 | 0.31 ± 0.04 | 0.25 ± 0.25 | 0.50 ± 0.25 | 0.35 ± 0.07 | 1 ± 0.15 | 17.1 ± 3.31 | 11,632 ± 1367.75 | 5.54 ± 0.87 | 0.36 ± 0.03 | 0 | 1 |
| prime-base-deep | 10 | 0.66 ± 0.09 | 0.74 ± 0.11 | 0.63 ± 0.09 | 0.95 ± 0.01 | 0.94 ± 0.01 | 1.00 ± 0.00 | 0.88 ± 0.12 | 0.82 ± 0.01 | 25 ± 1.10 | 194.0 ± 1.21 | 455,410 ± 669.95 | 0.29 ± 0.06 | 0.69 ± 0.08 | 0 | 0 |

_Metric columns average 2 passes; `n` is questions per pass; judge errors and failed runs are totals over all passes. A failed run includes a completed run that returned no answer._

## PRIME + GEPA

GEPA (task 3.1) optimized plan and judge with 16 metric calls and made 1 proposal; the best scored 0.71 on dev. The base prompts scored 0.75 on dev (`reports/gepa-run.json`).
No candidate beat base on dev, so GEPA wrote no optimized prompts and PRIME + GEPA is `prime-base-deep`. It was not run separately; its lift is 0 by construction (docs/05 §5).

## PRD targets (docs/00 §9)

| config | metric | subset | value | n | target | met |
|---|---|---|---|---|---|---|
| baseline-none-deep | contradiction_handling | tier 4 with expected contradictions | 0.50 | 1 | 0.60 | no |
| baseline-none-deep | currency | change-detection questions | 0.56 | 2 | 0.80 | no |
| baseline-none-deep | evidence_recall | all | 0.00 | 9 | 0.75 | no |
| baseline-none-deep | citation_correctness | all | 0.00 | 10 | 0.85 | no |
| prime-base-deep | contradiction_handling | tier 4 with expected contradictions | 1.00 | 1 | 0.60 | yes |
| prime-base-deep | currency | change-detection questions | 0.69 | 2 | 0.80 | no |
| prime-base-deep | evidence_recall | all | 0.74 | 9 | 0.75 | no |
| prime-base-deep | citation_correctness | all | 0.63 | 10 | 0.85 | no |
| prime-base-deep | answer_correctness | delta over baseline | 0.02 | 10 | 0.25 | no |
| prime-base-deep | gepa_lift | no optimized prompts (equals base) | 0.00 | 10 | 0.05 | no |

## Per tier

_From the latest pass of each configuration; the headline and PRD targets average all 2 passes._

| tier | config | n | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency | composite |
|---|---|---|---|---|---|---|---|---|
| 2 | baseline-none-deep | 3 | 1.00 | 0.00 | 0.00 | 0.08 | 0.50 | 0.55 |
| 3 | baseline-none-deep | 5 | 0.58 | 0.00 | 0.00 | 0.24 | 0.25 | 0.30 |
| 4 | baseline-none-deep | 2 | 0.50 | 0.00 | 0.00 | 0.07 | 0.00 | 0.35 |
| 2 | prime-base-deep | 3 | 0.68 | 0.56 | 0.68 | 1.00 | 1.00 | 0.66 |
| 3 | prime-base-deep | 5 | 0.45 | 0.60 | 0.45 | 0.91 | 0.85 | 0.51 |
| 4 | prime-base-deep | 2 | 0.68 | 1.00 | 0.57 | 1.00 | 1.00 | 0.78 |

## Per domain

_From the latest pass of each configuration; the headline and PRD targets average all 2 passes._

| domain | config | n | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency | composite |
|---|---|---|---|---|---|---|---|---|
| cgm | baseline-none-deep | 4 | 0.68 | 0.00 | 0.00 | 0.10 | 0.12 | 0.34 |
| cross | baseline-none-deep | 2 | 0.80 | 0.00 | 0.00 | 0.27 | 0.50 | 0.45 |
| glp1 | baseline-none-deep | 3 | 0.53 | 0.00 | 0.00 | 0.17 | 0.42 | 0.30 |
| other | baseline-none-deep | 1 | 1.00 | — | 0.00 | 0.13 | 0.00 | 0.70 |
| cgm | prime-base-deep | 4 | 0.50 | 0.67 | 0.46 | 0.94 | 1.00 | 0.59 |
| cross | prime-base-deep | 2 | 0.64 | 0.50 | 0.69 | 0.91 | 1.00 | 0.65 |
| glp1 | prime-base-deep | 3 | 0.46 | 0.67 | 0.46 | 1.00 | 0.75 | 0.49 |
| other | prime-base-deep | 1 | 1.00 | — | 0.86 | 1.00 | 1.00 | 0.96 |

## Per question

_From the latest pass of each configuration; the headline and PRD targets average all 2 passes._

| question | config | composite | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency | status | trace |
|---|---|---|---|---|---|---|---|---|---|
| adv-cgm-002 | baseline-none-deep | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbd-ebdb-7993-801f-991ce12c68f2/run/01a09dbd-ebdb-7993-801f-991ce12c68f2?start_time=2026-09-14T02%3A27%3A44.731588%2B00%3A00) |
| adv-cgm-002 | prime-base-deep | 0.60 | 0.37 | 1.00 | 0.29 | 1.00 | 1.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd2-854d-78d1-8ab6-3c07fa59aceb/run/01a09dd2-854d-78d1-8ab6-3c07fa59aceb?start_time=2026-09-14T02%3A50%3A14.733692%2B00%3A00) |
| cgm-code-004 | baseline-none-deep | 0.29 | 0.73 | 0.00 | 0.00 | 0.23 | 0.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbe-08eb-7c33-9dd0-59fa4830165b/run/01a09dbe-08eb-7c33-9dd0-59fa4830165b?start_time=2026-09-14T02%3A27%3A52.171748%2B00%3A00) |
| cgm-code-004 | prime-base-deep | 0.36 | 0.27 | 0.00 | 0.38 | 0.75 | 1.00 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd4-d43a-74c2-b21d-9614df27e43b/run/01a09dd4-d43a-74c2-b21d-9614df27e43b?start_time=2026-09-14T02%3A52%3A46.010921%2B00%3A00) |
| cgm-elig-003 | baseline-none-deep | 0.50 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbe-53fa-7153-8f65-a84eee11d6b1/run/01a09dbe-53fa-7153-8f65-a84eee11d6b1?start_time=2026-09-14T02%3A28%3A11.386187%2B00%3A00) |
| cgm-elig-003 | prime-base-deep | 0.93 | 1.00 | 1.00 | 0.80 | 1.00 | 1.00 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd8-0df8-7893-aca9-096a5ecf5468/run/01a09dd8-0df8-7893-aca9-096a5ecf5468?start_time=2026-09-14T02%3A56%3A17.400498%2B00%3A00) |
| cgm-elig-006 | baseline-none-deep | 0.55 | 1.00 | 0.00 | 0.00 | 0.15 | 0.50 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbe-34a0-7aa3-8b2d-108e9ddac15f/run/01a09dbe-34a0-7aa3-8b2d-108e9ddac15f?start_time=2026-09-14T02%3A28%3A03.360053%2B00%3A00) |
| cgm-elig-006 | prime-base-deep | 0.48 | 0.37 | 0.67 | 0.38 | 1.00 | 1.00 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd7-c33f-7d81-8de3-1f0fcdccbeef/run/01a09dd7-c33f-7d81-8de3-1f0fcdccbeef?start_time=2026-09-14T02%3A55%3A58.271573%2B00%3A00) |
| chg-glp1-001 | baseline-none-deep | 0.10 | 0.10 | 0.00 | 0.00 | 0.07 | 0.50 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbd-ebdd-7ae2-a264-fd8b0b7638e2/run/01a09dbd-ebdd-7ae2-a264-fd8b0b7638e2?start_time=2026-09-14T02%3A27%3A44.733788%2B00%3A00) |
| chg-glp1-001 | prime-base-deep | 0.22 | 0.37 | 0.00 | 0.12 | 1.00 | 0.50 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd2-854e-7891-b6c2-3992217b7b0e/run/01a09dd2-854e-7891-b6c2-3992217b7b0e?start_time=2026-09-14T02%3A50%3A14.734097%2B00%3A00) |
| chg-glp1-003 | baseline-none-deep | 0.32 | 0.48 | 0.00 | 0.00 | 0.23 | 0.75 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbe-8547-7dc0-b93e-aa8c306cc96c/run/01a09dbe-8547-7dc0-b93e-aa8c306cc96c?start_time=2026-09-14T02%3A28%3A24.007695%2B00%3A00) |
| chg-glp1-003 | prime-base-deep | 0.61 | 0.58 | 1.00 | 0.38 | 1.00 | 0.75 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dda-c6d1-76d2-b624-cd8f728b210d/run/01a09dda-c6d1-76d2-b624-cd8f728b210d?start_time=2026-09-14T02%3A59%3A15.793978%2B00%3A00) |
| cross-002 | baseline-none-deep | 0.60 | 1.00 | 0.00 | 0.00 | 0.10 | 1.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbe-5d8c-7643-a61a-bf41e7382e34/run/01a09dbe-5d8c-7643-a61a-bf41e7382e34?start_time=2026-09-14T02%3A28%3A13.836144%2B00%3A00) |
| cross-002 | prime-base-deep | 0.58 | 0.68 | 0.00 | 0.88 | 1.00 | 1.00 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd8-21d4-7c62-96e9-9ccdd1acb5dc/run/01a09dd8-21d4-7c62-96e9-9ccdd1acb5dc?start_time=2026-09-14T02%3A56%3A22.484326%2B00%3A00) |
| cross-003 | baseline-none-deep | 0.29 | 0.60 | 0.00 | 0.00 | 0.44 | 0.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbe-1667-70f2-bc47-0accf5d32752/run/01a09dbe-1667-70f2-bc47-0accf5d32752?start_time=2026-09-14T02%3A27%3A55.623230%2B00%3A00) |
| cross-003 | prime-base-deep | 0.73 | 0.60 | 1.00 | 0.50 | 0.82 | 1.00 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd5-193b-79b1-9ce5-0416bb3c4293/run/01a09dd5-193b-79b1-9ce5-0416bb3c4293?start_time=2026-09-14T02%3A53%3A03.675747%2B00%3A00) |
| glp1-path-004 | baseline-none-deep | 0.50 | 1.00 | 0.00 | 0.00 | 0.22 | 0.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbd-ebe0-7311-9da3-5a9d5e48f656/run/01a09dbd-ebe0-7311-9da3-5a9d5e48f656?start_time=2026-09-14T02%3A27%3A44.736296%2B00%3A00) |
| glp1-path-004 | prime-base-deep | 0.65 | 0.42 | 1.00 | 0.88 | 1.00 | 1.00 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd2-854e-71b0-a3db-ca72ea53187e/run/01a09dd2-854e-71b0-a3db-ca72ea53187e?start_time=2026-09-14T02%3A50%3A14.734610%2B00%3A00) |
| oos-002 | baseline-none-deep | 0.70 | 1.00 | — | 0.00 | 0.13 | 0.00 | completed | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbe-1c9f-7e23-b3ce-246956144c7b/run/01a09dbe-1c9f-7e23-b3ce-246956144c7b?start_time=2026-09-14T02%3A27%3A57.215278%2B00%3A00) |
| oos-002 | prime-base-deep | 0.96 | 1.00 | — | 0.86 | 1.00 | 1.00 | budget_exhausted | [trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd5-380c-7320-848d-dc25373a9072/run/01a09dd5-380c-7320-848d-dc25373a9072?start_time=2026-09-14T02%3A53%3A11.564295%2B00%3A00) |

## Worked examples

_From the latest pass of each configuration; the headline and PRD targets average all 2 passes._

### Easy: `cgm-elig-003` (tier 2, eligibility)

**Question.** What practitioner visit requirements must be met for initial and continued Medicare coverage of a CGM?

**Answer key.** Initial coverage requires an in-person or Medicare-approved telehealth visit with the treating practitioner within six months prior to ordering, to evaluate diabetes control and determine criteria are met. Continued coverage requires a visit every six months following the initial prescription to assess adherence to the CGM regimen and diabetes treatment plan.

| config | composite | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency |
|---|---|---|---|---|---|---|
| baseline-none-deep | 0.50 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| prime-base-deep | 0.93 | 1.00 | 1.00 | 0.80 | 1.00 | 1.00 |

**baseline-none-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbe-53fa-7153-8f65-a84eee11d6b1/run/01a09dbe-53fa-7153-8f65-a84eee11d6b1?start_time=2026-09-14T02%3A28%3A11.386187%2B00%3A00))

> For Medicare to cover a continuous glucose monitor (CGM), the following practitioner visit requirements must be met:
>
> ## Initial Coverage
> Within **six months prior to ordering the CGM**, the treating practitioner must conduct an **in-person or Medicare-approved telehealth visit** with the beneficiary. During this visit, the practitioner must evaluate the patient’s diabetes control and document that all coverage criteria are met (diabetes diagnosis, insulin treatment or history of problematic hypoglycemia, etc.).
>
> ## Continued Coverage
> Every **six months following the initial prescription**, the treating practitioner must conduct an **in-person or Medicare-approved telehealth visit** with the beneficiary to:
> - Assess adherence to the CGM regimen
> - Review and document the diabetes treatment plan
>
> ## Important Notes
> - **Treating practitioner requirement:** The visit must be conducted by the treating practitioner (e.g., physician, NP, PA). A pharmacist is **not** considered a statutorily recognized treating practitioner for Medicare CGM documentation purposes.
> - **Telehealth allowed:** Medicare-approved telehealth visits satisfy the requirement; they do not need to be solely in-person.
> - **Medical record documentation:** The visit must be sufficiently documented in the medical record to support continued necessity.
>
> **Sources:**
> - [CMS Glucose Monitor Policy Article (A52464)](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleId=52464)
> - [Noridian — Continued Coverage for CGM](https://med.noridianmedicare.com/web/jddme/article-detail/-/view/2230715/continued-coverage-for-continuous-glucose-monitor-cgm-)
> - [CGS Medicare CGM Documentation Checklist (PDF)](https://cgsmedicare.com/jc/checklists/cgms.pdf)
> - [AAFP — Medicare Coverage of CGM](https://www.aafp.org/fpm/2024/0100/continuous-glucose-monitoring)
> - [Dexcom Medicare FAQs](https://www.dexcom.com/en-us/faqs/medicare)

**prime-base-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd8-0df8-7893-aca9-096a5ecf5468/run/01a09dd8-0df8-7893-aca9-096a5ecf5468?start_time=2026-09-14T02%3A56%3A17.400498%2B00%3A00))

> ## Answer
> For initial Medicare coverage of a CGM, the beneficiary must have an in‑person or Medicare‑approved telehealth visit with the treating practitioner within 6 months before ordering the device to evaluate diabetes control and to confirm that the beneficiary (or caregiver) has sufficient training on the CGM. For continued coverage, a treating practitioner visit (in‑person or Medicare‑approved telehealth) is required every 6 months after the initial prescription to document adherence to the CGM regimen and diabetes treatment plan. These requirements are set forth in LCD L33822 (effective 2024‑10‑01) and reinforced by Article A52464 (effective 2025‑02‑18).
>
> ## Criteria / Details
> - **Initial coverage – diabetes‑control visit:** In‑person or Medicare‑approved telehealth visit within 6 months prior to ordering the CGM to evaluate the beneficiary’s diabetes control.[5][8][9] 
> - **Initial coverage – training criterion:** Treating practitioner must conclude that the beneficiary (or beneficiary’s caregiver) has sufficient training using the prescribed CGM.[10] 
> - **Continued coverage – adherence visit:** In‑person or Medicare‑approved telehealth visit every 6 months after the initial prescription to document adherence to the CGM regimen and diabetes treatment plan.[1][3] 
> - **Supplies billing documentation (for context):** Suppliers may bill HCPCS A4238 or A4239 monthly only if sufficient supplies have been delivered to last 30 days after the claim date of service.[7] 
>

### Contradiction: `adv-cgm-002` (tier 4, contradiction)

**Question.** I read that Medicare requires three or more insulin injections per day before it will cover a CGM. Is that still true?

**Answer key.** No. That requirement existed before April 16, 2023 and was removed by the LCD revision; any source stating it is out of date. Current criteria: insulin treatment (any regimen) or problematic hypoglycemia.

| config | composite | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency |
|---|---|---|---|---|---|---|
| baseline-none-deep | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| prime-base-deep | 0.60 | 0.37 | 1.00 | 0.29 | 1.00 | 1.00 |

**baseline-none-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbd-ebdb-7993-801f-991ce12c68f2/run/01a09dbd-ebdb-7993-801f-991ce12c68f2?start_time=2026-09-14T02%3A27%3A44.731588%2B00%3A00))

> (no answer: the run completed without answer text, and it is scored as a failed run)

**prime-base-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd2-854d-78d1-8ab6-3c07fa59aceb/run/01a09dd2-854d-78d1-8ab6-3c07fa59aceb?start_time=2026-09-14T02%3A50%3A14.733692%2B00%3A00))

> ## Answer
> No. As of the April 2023 revision to LCD L33822 (still in effect in the October 1, 2024 version), Medicare no longer requires three or more insulin injections per day for CGM coverage; the current criterion only requires that the beneficiary be insulin‑treated, with no specific injection‑frequency minimum[2][7].
>
> ## Criteria / Details
> - Beneficiary must be insulin‑treated (either using multiple daily injections or a continuous subcutaneous insulin infusion pump)[7].
> - No minimum number of insulin injections per day is specified[11].
> - The requirement for “multiple (three or more) daily administrations of insulin or a CSII pump” was removed from the CGM coverage criterion in the April 2023 revision[2][9].
>

### Out of scope: `oos-002` (tier 4, out_of_scope)

**Question.** My patient has type 2 diabetes and takes only metformin — can you approve a CGM for them?

**Answer key.** The system must not adjudicate an individual; it answers at the policy level (the L33822 criteria for a non-insulin beneficiary) and states that coverage determinations are made by the payer based on the medical record.

| config | composite | answer_correctness | evidence_recall | citation_correctness | citation_completeness | currency |
|---|---|---|---|---|---|---|
| baseline-none-deep | 0.70 | 1.00 | — | 0.00 | 0.13 | 0.00 |
| prime-base-deep | 0.96 | 1.00 | — | 0.86 | 1.00 | 1.00 |

**baseline-none-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dbe-1c9f-7e23-b3ce-246956144c7b/run/01a09dbe-1c9f-7e23-b3ce-246956144c7b?start_time=2026-09-14T02%3A27%3A57.215278%2B00%3A00))

> I'll search for current CGM coverage criteria for type 2 diabetes patients, particularly regarding insulin use requirements.  **No.** Under current Medicare criteria—and most commercial insurance policies modeled on them—a patient with type 2 diabetes who takes **only metformin** generally **does not qualify** for insurance-covered CGM unless they have separately documented problematic hypoglycemia.
>
> **Current Medicare coverage criteria (and most major insurers) require ONE of the following:**
>
> | Pathway | Requirement | Source |
> |--------|-------------|--------|
> | **A** | The patient is **treated with insulin** (any type, any amount). | [Dexcom / Medicare criteria](https://www.dexcom.com/en-us/faqs/medicare) |
> | **B** | The patient has **documented problematic hypoglycemia** despite medication adjustments:<br>• Recurrent Level 2 events (<54 mg/dL) persisting after ≥2 treatment modifications, **or**<br>• One Level 3 event (<54 mg/dL) requiring third-party assistance due to altered mental/physical state. | [CMS criteria via PMC/MLN](https://pmc.ncbi.nlm.nih.gov/articles/PMC11307217); [CMS.gov](https://www.cms.gov/training-education/medicare-learning-networkr-mln/compliance/medicare-provider-compliance-tips/glucose-monitoring-supplies) |
>
> **Why metformin-only usually fails:**
> - Metformin does **not** cause hypoglycemia, so Pathway B is inherently unlikely.
> - No insulin use means Pathway A is not met.
>
> **Options for the patient:**
> 1. **Self-pay** for CGM out of pocket.
> 2. **Appeal/exceptions process** through their specific insurer (some commercial plans have broader criteria than Medicare).
> 3. **Monitor for hypoglycemia** if clinical suspicion exists (e.g., reactive hypoglycemia, other comorbidities), document properly, and re-evaluate—but this should not be fabricated solely to obtain device coverage.
>
> *Note: I cannot "approve" coverage; I am summarizing payer criteria. Final authorization depends on the specific insurer and documented medical necessity.*

**prime-base-deep** ([trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dd5-380c-7320-848d-dc25373a9072/run/01a09dd5-380c-7320-848d-dc25373a9072?start_time=2026-09-14T02%3A53%3A11.564295%2B00%3A00))

> ## Answer
> This asks whether a specific patient qualifies for coverage, which depends on that patient's full clinical record; the answer below covers only the Medicare policy rule for CGM coverage, not an individual approval decision. 
> Under Medicare policy, a beneficiary with type 2 diabetes who is treated only with metformin (non‑insulin) does not automatically qualify for a therapeutic CGM; coverage requires either insulin treatment or a documented history of problematic hypoglycemia [9][10][5][6]. 
> If the patient has no documented hypoglycemia episodes, they would not meet the current Medicare criteria for CGM coverage.
>
> ## Criteria / Details
> - The beneficiary must be insulin‑treated **or** have a history of problematic hypoglycemia [9][10]. 
> - For non‑insulin patients, qualification depends solely on a documented history of problematic hypoglycemia [10][5][6]. 
> - Documentation must show the beneficiary is testing at a frequency that corroborates the quantity of CGM supplies dispensed [3][16]. 
> - Therapeutic CGM coverage requires the patient to be insulin treated **or** have a history of problematic hypoglycemia with documentation [5].
>

## Cost and latency

_From the latest pass of each configuration; the headline and PRD targets average all 2 passes._

| config | search_cost mean | median | latency_s mean | median | tokens mean | median | search_efficiency mean | median | agent tokens total | judge tokens total |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline-none-deep | 1 | 1 | 13.8 | 12.8 | 10,264 | 9,247 | 6.41 | 6.67 | 102,639 | 340,919 |
| prime-base-deep | 26 | 27 | 195.2 | 191.6 | 456,080 | 453,286 | 0.23 | 0.20 | 4,560,795 | 712,900 |

## Evaluator comments

_From the latest pass of each configuration; the headline and PRD targets average all 2 passes._

### `adv-cgm-002`

**baseline-none-deep**

- `answer_correctness` 0.00 — run failed: completed
- `evidence_recall` 0.00 — run failed: completed
- `citation_correctness` 0.00 — run failed: completed
- `citation_completeness` 0.00 — run failed: completed
- `currency` 0.00 — run failed: completed
- `contradiction_handling` 0.00 — run failed: completed
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.00 — run failed: completed
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 13.0 — 13.0s wall clock
- `tokens` 9,162 — 8064 in + 1098 out
- `search_efficiency` 0.00 — answer_correctness 0.0 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.37 — claims 2/6 weighted present; missing: c2 (must), c3 (must); summary: partial
- `evidence_recall` 1.00 — matched e1 (must) via id (ev_f2e02660ce)
- `citation_correctness` 0.29 — 2/7 sampled cited sentences supported (of 7 cited); failing: [2][7] 'No. As of the April 2023 revision to LCD L33822 (still in effect in...' - The April 2023 revision date is not mentioned in the cited passages or their Document lines.; [7] 'Beneficiary must be insulin‑treated (either using multiple daily in...' - Passage [7] states only that the beneficiary is insulin-treated and does not include the parenthe...; [2][9] 'The requirement for “multiple (three or more) daily administrations...' - The April 2023 revision date is not mentioned in the cited passages or their Document lines.; [2][7][11] 'No substantive contradictions exist among the primary policy source...' - The April 2023 date is absent from the cited passages and their Document lines, and the passages ...; [3][6] 'The reviewer noted that some secondary sources (Aeroflow Diabetes, ...' - The cited secondary-source passages do not state that they are consistent with primary sources or...
- `citation_completeness` 1.00 — 4/4 cited in Criteria / Details and Codes and documentation
- `currency` 1.00 — L33822: cited; governing date 2024-10-01 stated
- `contradiction_handling` 1.00 — x1 'Older pages state the MDI requirement; the current LCD do...': surfaced, governing stated
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.71 — 5/7 citations at official_secondary or better; below: [3] unknown aeroflowdiabetes.com, [6] unknown aarp.org
- `search_cost` 13 — 7 searches + 6 fetches
- `latency_s` 151.3 — 151.3s wall clock
- `tokens` 294,375 — 260142 in + 34233 out
- `search_efficiency` 0.28 — answer_correctness 0.3667 / max(1, 13 calls) x 10

### `cgm-code-004`

**baseline-none-deep**

- `answer_correctness` 0.73 — claims 2/3 weighted present; missing: c2; summary: consistent
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.23 — 3/13 cited in whole answer (no Criteria / Codes sections); uncited: 'No. **If a Medicare beneficiary uses a smartphone as the *only* display devic...'; 'Medicare covers CGM supplies **only when the patient uses a standalone receiv...'; 'Patients **may also use** a smartphone, smartwatch, or other personal device ...'
- `currency` 0.00 — A52464: not cited; governing date 2025-02-18 not stated
- `contradiction_handling` 0.00 — x1 'Vendor guidance may differ from the article': not surfaced
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.00 — 0/3 citations at official_secondary or better; below: [1] web dexcom.com, [2] unknown priorityhealth.com, [3] unknown aafp.org
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 11.2 — 11.2s wall clock
- `tokens` 7,849 — 6948 in + 901 out
- `search_efficiency` 7.33 — answer_correctness 0.7333 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.27 — claims 1/3 weighted present; incorrect: c1 (must) - The answer asserts the article is silent on smartphone display, which contradicts the key stating the article address...; summary: inconsistent
- `evidence_recall` 0.00 — unmatched e1 (must) [A52464: document found, no passage containing 'smartphone', 'receiver']
- `citation_correctness` 0.38 — 3/8 sampled cited sentences supported (of 10 cited); failing: [6][9][5] 'The LCD L33822 and Article A52464 state that when a CGM (E2102/E210...' - The passages do not include Article A52464, so the claim that Article A52464 states that the rela...; [4] 'No primary policy document in the evidence confirms that using a sm...' - Passage [4] does not state that no primary policy document confirms using a smartphone satisfies ...; [5] 'The 10/01/2024 revision of LCD L33822 only updated the long descrip...' - The passage does not state that the revision was limited only to the long descriptor for A4271 or...; [4][5][6] 'The non‑CMS source (Aeroflow Diabetes) suggests possible coverage w...' - The passages do not include Article A52464, and they do not state that primary policy governs or ...; [5] 'LCD L33822’s silence on smartphone display leaves uncertainty about...' - The passage does not mention smartphone display, uncertainty about a dedicated receiver, or the a...
- `citation_completeness` 0.75 — 6/8 cited in Criteria / Details and Codes and documentation; uncited: 'HCPCS codes for CGM devices: **E2102** (adjunctive) and **E2103** (non‑adjunc...'; 'HCPCS codes for supply allowance: **A4238** (adjunctive CGM) and **A4239** (n...'
- `currency` 1.00 — A52464: cited; governing date 2025-02-18 stated
- `contradiction_handling` 1.00 — x1 'Vendor guidance may differ from the article': surfaced, governing stated
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.88 — 7/8 citations at official_secondary or better; below: [4] unknown aeroflowdiabetes.com
- `search_cost` 25 — 14 searches + 11 fetches
- `latency_s` 192.3 — 192.3s wall clock
- `tokens` 494,407 — 440727 in + 53680 out
- `search_efficiency` 0.11 — answer_correctness 0.2667 / max(1, 25 calls) x 10

### `cgm-elig-003`

**baseline-none-deep**

- `answer_correctness` 1.00 — claims 5/5 weighted present; summary: consistent
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.00 — 0/11 cited in whole answer (no Criteria / Codes sections); uncited: 'For Medicare to cover a continuous glucose monitor (CGM), the following pract...'; 'Within **six months prior to ordering the CGM**, the treating practitioner mu...'; 'During this visit, the practitioner must evaluate the patient’s diabetes cont...'
- `currency` 0.00 — L33822: not cited; governing date 2024-10-01 not stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.60 — 3/5 citations at official_secondary or better; below: [4] unknown aafp.org, [5] web dexcom.com
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 12.6 — 12.6s wall clock
- `tokens` 8,514 — 7650 in + 864 out
- `search_efficiency` 10.00 — answer_correctness 1.0 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 1.00 — claims 5/5 weighted present; summary: consistent
- `evidence_recall` 1.00 — matched e1 (must) via id (ev_5eb3d0d516)
- `citation_correctness` 0.80 — 4/5 sampled cited sentences supported (of 5 cited); failing: [7] 'HCPCS A4238/A4239 monthly billing requires proof of a 30‑day supply...' - The passage does not mention 'proof' or that a 30‑day supply must be 'on hand'; it states that th...
- `citation_completeness` 1.00 — 5/5 cited in Criteria / Details and Codes and documentation
- `currency` 1.00 — L33822: cited; governing date 2024-10-01 stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 1.00 — 7/7 citations at official_secondary or better
- `search_cost` 29 — 16 searches + 13 fetches
- `latency_s` 187.9 — 187.9s wall clock
- `tokens` 438,815 — 386950 in + 51865 out
- `search_efficiency` 0.34 — answer_correctness 1.0 / max(1, 29 calls) x 10

### `cgm-elig-006`

**baseline-none-deep**

- `answer_correctness` 1.00 — claims 6/6 weighted present; summary: consistent
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.15 — 4/26 cited in whole answer (no Criteria / Codes sections); uncited: '**Yes.** Under Medicare, a nurse practitioner is explicitly considered a "tre...'; 'Per 42 CFR § 410.38, a "treating practitioner" includes a physician, physicia...'; 'This is consistent across CGM Local Coverage Determinations (LCDs) and policy...'
- `currency` 0.50 — L33822: cited; governing date 2024-10-01 not stated; A52464: cited; governing date 2025-02-18 not stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 1.00 — 5/5 citations at official_secondary or better
- `search_cost` 2 — 2 searches + 0 fetches
- `latency_s` 21.7 — 21.7s wall clock
- `tokens` 21,257 — 19474 in + 1783 out
- `search_efficiency` 5.00 — answer_correctness 1.0 / max(1, 2 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.37 — claims 2/6 weighted present; missing: c1 (must), c3 (must); summary: partial
- `evidence_recall` 0.67 — matched e1 (must) via id (ev_98816cd24f) | unmatched e2 [A52464: document found, no passage containing 'standard written order']
- `citation_correctness` 0.38 — 3/8 sampled cited sentences supported (of 13 cited); failing: [6] 'Under Medicare policy, a nurse practitioner may order a continuous ...' - The passage only records the replacement of "physician" with "treating practitioner" in LCD L3382...; [6] '**Treating practitioner requirement:** LCD L33822 was revised to re...' - The passage does not indicate that non-physician clinicians such as nurse practitioners may be el...; [1] '**Face‑to‑face/telehealth encounter:** Final Rule 1713 mandates a f...' - The passage states that Final Rule 1713 requires a face-to-face encounter but does not mention a ...; [2] 'General order content (patient information, practitioner details, d...' - The passage refers to A55426 for general documentation requirements but does not specify that pat...; [2] 'Specific diagnosis codes (e.g., E11.*) or other patient‑information...' - The passage does not mention specific diagnosis codes or state that Article A55426 was not review...
- `citation_completeness` 1.00 — 9/9 cited in Criteria / Details and Codes and documentation
- `currency` 1.00 — L33822: cited; governing date 2024-10-01 stated; A52464: cited; governing date 2025-02-18 stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 1.00 — 4/4 citations at official_secondary or better
- `search_cost` 23 — 14 searches + 9 fetches
- `latency_s` 197.5 — 197.5s wall clock
- `tokens` 447,212 — 402707 in + 44505 out
- `search_efficiency` 0.16 — answer_correctness 0.3667 / max(1, 23 calls) x 10

### `chg-glp1-001`

**baseline-none-deep**

- `answer_correctness` 0.10 — claims 0/6 weighted present; missing: c1 (must), c3 (must); incorrect: c2 (must) - Every source cited is secondary; none are primary CMS, HHS, or FDA sources.; summary: partial
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.07 — 1/14 cited in whole answer (no Criteria / Codes sections); uncited: 'The biggest change in 2026 was the launch of the **Medicare GLP-1 Bridge prog...'; 'Here are the key details:'; '**What changed:** Medicare historically barred coverage for medications presc...'
- `currency` 0.50 — CMS 2026 announcements: not cited; no governing date on record (search-guessed index entry); order: ordered_with_dates (The answer identifies the main 2026 change—the launch of the Medicare GLP-1 Bridge program—and gives its effective da...)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.00 — 0/4 citations at official_secondary or better; below: [1] unknown forbes.com, [2] web goodrx.com, [3] unknown cbsnews.com, [4] professional kff.org
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 11.4 — 11.4s wall clock
- `tokens` 9,417 — 8335 in + 1082 out
- `search_efficiency` 1.00 — answer_correctness 0.1 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.37 — claims 2/6 weighted present; missing: c1 (must), c3 (must); summary: partial
- `evidence_recall` 0.00 — unmatched e1 (must) [CMS 2026 announcements: no evidence from this document] | search-guessed descriptor (needs_review): e1
- `citation_correctness` 0.12 — 1/8 sampled cited sentences supported (of 8 cited); failing: [6][2][5] 'In March 2026 Medicare introduced the GLP‑1 Bridge demonstration pr...' - Passage [6] states CMS released a memorandum related to the Bridge on March 3, 2026, but does not...; [4] 'This represents a change from prior coverage, where such drugs were...' - Passage [4] only lists an effective date for NCD 38 and does not mention prior Part D coverage, e...; [6] 'The Medicare GLP‑1 Bridge was established by a CMS HPMS memorandum ...' - Passage [6] says CMS released a memorandum to provide FAQs related to the Bridge, not that the me...; [5] 'The Bridge operates under demonstration authority [5].' - Passage [5] mentions "the demonstration" but does not state that the Bridge operates under demons...; [4] 'No 2026 revision was made to NCD 38 (Treatment of Obesity), which h...' - Passage [4] shows an effective date of 09/24/2013 but does not state that no 2026 revision was made.; [4] 'While the GLP‑1 Bridge expands coverage for certain GLP‑1 agonists,...' - Passage [4] contains no information about the GLP-1 Bridge or any 2026 revision to the NCD.; [5] 'The Bridge is a demonstration program, not a permanent statutory ch...' - Passage [5] does not mention permanence, statutory status, or the possibility of altering authori...
- `citation_completeness` 1.00 — 4/4 cited in Criteria / Details and Codes and documentation
- `currency` 0.50 — CMS 2026 announcements: not cited; no governing date on record (search-guessed index entry); order: ordered_with_dates (The answer identifies a single 2026 change—the GLP-1 Bridge demonstration program—and gives its specific effective da...)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 1.00 — 7/7 citations at official_secondary or better
- `search_cost` 34 — 20 searches + 14 fetches
- `latency_s` 176.8 — 176.8s wall clock
- `tokens` 446,152 — 389964 in + 56188 out
- `search_efficiency` 0.11 — answer_correctness 0.3667 / max(1, 34 calls) x 10

### `chg-glp1-003`

**baseline-none-deep**

- `answer_correctness` 0.48 — claims 3/5 weighted present; missing: c1 (must); summary: inconsistent
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.23 — 3/13 cited in whole answer (no Criteria / Codes sections); uncited: 'The CMS Innovation Center model is called the **BALANCE Model** (Better Appro...'; 'It is a voluntary, five-year model in which CMS negotiates directly with manu...'; '**Launch dates:**'
- `currency` 0.75 — CMS Innovation Center model page: cited; no governing date on record (search-guessed index entry); order: dated_not_ordered (The answer includes multiple dated changes but presents them out of chronological order, listing July 2026 after Janu...)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.67 — 2/3 citations at official_secondary or better; below: [2] professional kff.org
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 10.8 — 10.8s wall clock
- `tokens` 8,348 — 7349 in + 999 out
- `search_efficiency` 4.80 — answer_correctness 0.48 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.58 — claims 3/5 weighted present; missing: c1 (must); summary: partial
- `evidence_recall` 1.00 — matched e1 (must) via host+type (ev_4bbaace113) | search-guessed descriptor (needs_review): e1
- `citation_correctness` 0.38 — 3/8 sampled cited sentences supported (of 8 cited); failing: [1] 'The CMS Innovation Center model that addresses GLP-1 coverage is ca...' - The passage does not state that the model is a CMS Innovation Center model.; [14] 'For Medicare Part D, CMS indicates the BALANCE Model is expected to...' - The passage does not mention delays or extensions to the BALANCE Model launch.; [3][15][18] 'Medicaid eligibility and coverage pathways are defined under BALANC...' - The passages do not state that Medicaid eligibility and coverage pathways are defined under BALANCE.; [14][18] 'Medicare Part D coverage pathway is outlined, with an expected laun...' - The passages do not state that a Medicare Part D coverage pathway is outlined.; [12][17] 'The Medicare GLP-1 Bridge provides temporary access to certain GLP-...' - The cited passages do not state that the Medicare GLP-1 Bridge serves as a bridge to BALANCE.
- `citation_completeness` 1.00 — 5/5 cited in Criteria / Details and Codes and documentation
- `currency` 0.75 — CMS Innovation Center model page: cited; no governing date on record (search-guessed index entry); order: dated_not_ordered (The answer cites multiple specific dates—including May 2026, January 2027, and July 1, 2026—but presents them out of ...)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.84 — 16/19 citations at official_secondary or better; below: [7] unknown medicarerights.org, [8] unknown medicarerights.org, [9] professional kff.org
- `search_cost` 29 — 13 searches + 16 fetches
- `latency_s` 219.7 — 219.7s wall clock
- `tokens` 530,730 — 465257 in + 65473 out
- `search_efficiency` 0.20 — answer_correctness 0.58 / max(1, 29 calls) x 10

### `cross-002`

**baseline-none-deep**

- `answer_correctness` 1.00 — claims 5/5 weighted present; summary: consistent
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.10 — 2/21 cited in whole answer (no Criteria / Codes sections); uncited: 'A **CGM** and a **GLP-1 medication** fall under different parts of Medicare, ...'; 'Medicare covers continuous glucose monitors as **durable medical equipment (D...'; '**Cost sharing:** You pay **20% coinsurance** of the Medicare-approved amount...'
- `currency` 1.00 — Medicare.gov coverage pages: cited; no governing date on record (search-guessed index entry)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.20 — 1/5 citations at official_secondary or better; below: [1] unknown medicarefaq.com, [2] unknown coveredusa.org, [3] unknown brevy.com, [4] unknown pmc.ncbi.nlm.nih.gov
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 16.9 — 16.9s wall clock
- `tokens` 10,261 — 8427 in + 1834 out
- `search_efficiency` 10.00 — answer_correctness 1.0 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.68 — claims 3/5 weighted present; missing: c1 (must); summary: consistent
- `evidence_recall` 0.00 — unmatched e1 (must) [Medicare.gov CGM coverage page: descriptor resolves to no document]
- `citation_correctness` 0.88 — 7/8 sampled cited sentences supported (of 9 cited); failing: [1][11] 'Part D cost sharing for GLP‑1s follows the standard benefit: CY 202...' - The cited passages describe general Part D benefit features but do not mention GLP-1 medications,...
- `citation_completeness` 1.00 — 5/5 cited in Criteria / Details and Codes and documentation
- `currency` 1.00 — Medicare.gov coverage pages: cited; no governing date on record (search-guessed index entry)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.50 — 3/6 citations at official_secondary or better; below: [2] unknown brevy.com, [4] unknown brevy.com, [5] unknown brevy.com
- `search_cost` 33 — 19 searches + 14 fetches
- `latency_s` 273.3 — 273.3s wall clock
- `tokens` 529,596 — 462591 in + 67005 out
- `search_efficiency` 0.21 — answer_correctness 0.68 / max(1, 33 calls) x 10

### `cross-003`

**baseline-none-deep**

- `answer_correctness` 0.60 — claims 2/4 weighted present; missing: c2 (must); summary: consistent
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.44 — 8/18 cited in whole answer (no Criteria / Codes sections); uncited: 'I'll search for the current Medicare CGM coverage criteria, particularly rega...'; 'Medicare’s updated Local Coverage Determination (LCD L33822) creates two path...'; 'You qualify if you have diabetes **and** either:'
- `currency` 0.00 — L33822: not cited; governing date 2024-10-01 not stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` 0.50 — scope: not flagged; no fabricated payer criteria
- `primary_source_ratio` 0.00 — 0/4 citations at official_secondary or better; below: [1] unknown resources.tomorrowhealth.com, [2] unknown bcbsri.com, [3] unknown aeroflowdiabetes.com, [4] unknown wellrena.com
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 18.2 — 18.2s wall clock
- `tokens` 9,332 — 7587 in + 1745 out
- `search_efficiency` 6.00 — answer_correctness 0.6 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.60 — claims 2/4 weighted present; missing: c2 (must); summary: consistent
- `evidence_recall` 1.00 — matched e1 (must) via id (ev_2389a4fde1)
- `citation_correctness` 0.50 — 4/8 sampled cited sentences supported (of 11 cited); failing: [12] 'Policy Article A52464 specifies that a level‑3 hypoglycemic event r...' - Passage [12] does not mention a level‑3 hypoglycemic event.; [5][11] 'Documentation must include evidence of the hypoglycemic event (e.g....' - Neither passage [5] nor [11] mentions evidence of a hypoglycemic event or third‑party assistance.; [12] 'For a level‑3 hypoglycemic event: medical record showing third‑part...' - Passage [12] does not mention a level‑3 hypoglycemic event.; [1][4] 'Non‑CMS sources [1] and [4] are secondary and consistent with the p...' - The passages do not describe sources [1] and [4] as secondary or compare their weight to the LCD ...
- `citation_completeness` 0.82 — 9/11 cited in Criteria / Details and Codes and documentation; uncited: 'Eligibility is independent of GLP‑1 receptor agonist use; the determining fac...'; 'Required documentation:'
- `currency` 1.00 — L33822: cited; governing date 2024-10-01 stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` 1.00 — scope: scope_warning field; no fabricated payer criteria
- `primary_source_ratio` 0.82 — 9/11 citations at official_secondary or better; below: [1] unknown medicallymodern.com, [4] unknown doko.md
- `search_cost` 21 — 11 searches + 10 fetches
- `latency_s` 193.7 — 193.7s wall clock
- `tokens` 474,767 — 412504 in + 62263 out
- `search_efficiency` 0.29 — answer_correctness 0.6 / max(1, 21 calls) x 10

### `glp1-path-004`

**baseline-none-deep**

- `answer_correctness` 1.00 — claims 5/5 weighted present; summary: consistent
- `evidence_recall` 0.00 — baseline: citations are URLs with no stored passage, so no required evidence can be matched - 0 by construction
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.22 — 4/18 cited in whole answer (no Criteria / Codes sections); uncited: '**Yes, Medicare can cover Zepbound (tirzepatide) for obstructive sleep apnea ...'; 'After the FDA approved Zepbound for moderate-to-severe OSA in adults with obe...'; '**Typical requirements for coverage include:**'
- `currency` 0.00 — FDA Zepbound label: not cited; no governing date on record (search-guessed index entry); CMS 2024 Part D guidance: not cited; no governing date on record (search-guessed index entry)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.00 — 0/4 citations at official_secondary or better; below: [1] unknown drugs.com, [2] unknown nowpatient.com, [3] unknown understoodcare.com, [4] unknown formblends.com
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 7.9 — 7.9s wall clock
- `tokens` 8,884 — 8006 in + 878 out
- `search_efficiency` 10.00 — answer_correctness 1.0 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 0.42 — claims 2/5 weighted present; missing: c1 (must), c3; summary: partial
- `evidence_recall` 1.00 — matched e1 (must) via host+type (ev_b9c06a0ffb) | search-guessed descriptor (needs_review): e1
- `citation_correctness` 0.88 — 7/8 sampled cited sentences supported (of 13 cited); failing: [7][8] '**SAD List supersession:** Article A52800 (dated 2021-11-15) is out...' - The passages do not state that Article A52800 is outdated or that Article A52571 supersedes or go...
- `citation_completeness` 1.00 — 8/8 cited in Criteria / Details and Codes and documentation
- `currency` 1.00 — FDA Zepbound label: cited; no governing date on record (search-guessed index entry); CMS 2024 Part D guidance: cited; no governing date on record (search-guessed index entry)
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` — — not applicable: the answer key expects no scope warning
- `primary_source_ratio` 0.71 — 5/7 citations at official_secondary or better; below: [1] unknown ro.co, [4] unknown medicare.org
- `search_cost` 33 — 16 searches + 17 fetches
- `latency_s` 168.9 — 168.9s wall clock
- `tokens` 459,361 — 406787 in + 52574 out
- `search_efficiency` 0.13 — answer_correctness 0.42 / max(1, 33 calls) x 10

### `oos-002`

**baseline-none-deep**

- `answer_correctness` 1.00 — claims 4/4 weighted present; summary: consistent
- `evidence_recall` — — not applicable: the answer key requires no evidence
- `citation_correctness` 0.00 — baseline: citations are URLs with no stored passage to check a sentence against - 0 by construction
- `citation_completeness` 0.13 — 2/15 cited in whole answer (no Criteria / Codes sections); uncited: 'I'll search for current CGM coverage criteria for type 2 diabetes patients, p...'; '**Current Medicare coverage criteria (and most major insurers) require ONE of...'; '| Pathway | Requirement | Source |'
- `currency` 0.00 — L33822: not cited; governing date 2024-10-01 not stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` 1.00 — scope: stated in text; no fabricated payer criteria
- `primary_source_ratio` 0.33 — 1/3 citations at official_secondary or better; below: [1] web dexcom.com, [2] unknown pmc.ncbi.nlm.nih.gov
- `search_cost` 1 — 1 searches + 0 fetches
- `latency_s` 14.2 — 14.2s wall clock
- `tokens` 9,615 — 8438 in + 1177 out
- `search_efficiency` 10.00 — answer_correctness 1.0 / max(1, 1 calls) x 10

**prime-base-deep**

- `answer_correctness` 1.00 — claims 4/4 weighted present; summary: consistent
- `evidence_recall` — — not applicable: the answer key requires no evidence
- `citation_correctness` 0.86 — 6/7 sampled cited sentences supported (of 7 cited); failing: [3][16] 'Documentation must show the beneficiary is testing at a frequency t...' - Passage [16] refers to documentation requirements for problematic hypoglycemia, not to testing fr...
- `citation_completeness` 1.00 — 6/6 cited in Criteria / Details and Codes and documentation
- `currency` 1.00 — L33822: cited; governing date 2024-10-01 stated
- `contradiction_handling` — — not applicable: the answer key expects no contradiction
- `scope_handling` 1.00 — scope: scope_warning field; no fabricated payer criteria
- `primary_source_ratio` 0.90 — 9/10 citations at official_secondary or better; below: [6] unknown myrescuemd.com
- `search_cost` 23 — 14 searches + 9 fetches
- `latency_s` 190.9 — 190.9s wall clock
- `tokens` 445,380 — 397178 in + 48202 out
- `search_efficiency` 0.43 — answer_correctness 1.0 / max(1, 23 calls) x 10
