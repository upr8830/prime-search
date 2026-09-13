# cross-002 — validation worksheet

**Which part of Medicare covers a CGM versus a GLP-1 medication, and how does that affect cost sharing?**

`cross` · tier 2 · coverage_pathway · split `holdout`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [resolution] 'Medicare.gov coverage pages' has no canonical id; best search hit was http://www.cms.gov/Medicare/Coverage/CoverageGenInfo/index.html (official_secondary) — confirm this is the governing document
- [key_phrase] e1 cites 'Medicare.gov CGM coverage page', which is not in governing_documents — add it there or correct the evidence

## Draft summary

CGMs are covered as durable medical equipment under Part B (typically 20% coinsurance after the deductible, supplier must accept assignment); GLP-1s are covered under Part D plan formularies with plan-specific tiers, copays, and utilization management.

## Governing documents

- `Medicare.gov coverage pages` via **search** — [Medicare Coverage - General Information](http://www.cms.gov/Medicare/Coverage/CoverageGenInfo/index.html) · official_secondary · no date found · 236 paragraphs

## Required claims, against the live text

### c1 (**must**)

CGM is a Part B DME benefit

> *   [Part A cost report audit](http://www.cms.gov/medicare/audits-compliance/part-a-cost-report)
        *   [Part C/Part D compliance & audits](http://www.cms.gov/medicare/audits-compliance/part-c-d)

— `Medicare.gov coverage pages` §CMS.gov main menu ¶52

> *   [Original Medicare (Part A and B) Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/original-part-a-b)
        *   [Annual Medicare Participation Announcement](http://www.cms.gov/medicare-participation)
        *   [Providers & suppliers](http://www.cms.gov/medicare/enrollment-renewal/providers-suppliers)
        *   [Medicare Managed Care Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/managed-care-eligibility-enrollment)
        *   [Part D Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/part-d-enrollment-elig […]

— `Medicare.gov coverage pages` §CMS.gov main menu ¶19

> Back to  menu
### What is Medicaid?

— `Medicare.gov coverage pages` §CMS.gov main menu ¶68

### c2 (**must**)

GLP-1s are Part D drugs

> *   [Part A cost report audit](http://www.cms.gov/medicare/audits-compliance/part-a-cost-report)
        *   [Part C/Part D compliance & audits](http://www.cms.gov/medicare/audits-compliance/part-c-d)

— `Medicare.gov coverage pages` §CMS.gov main menu ¶52

> *   [Original Medicare appeals](http://www.cms.gov/medicare/appeals-grievances/fee-for-service)
        *   [Managed Care appeals & grievances](http://www.cms.gov/medicare/appeals-grievances/managed-care)
        *   [Medicare Prescription drug appeals & grievances](http://www.cms.gov/medicare/appeals-grievances/prescription-drug)
        *   [Ombudsman Center](http://www.cms.gov/medicare/appeals-grievances/ombudsman-center)
        *   [Appeals Decision Search (Part C & Part D)](http://www.cms.gov/medicare/appeals-grievances/appeals-decision-search-part-c-d)

— `Medicare.gov coverage pages` §CMS.gov main menu ¶37

> *   [Original Medicare (Part A and B) Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/original-part-a-b)
        *   [Annual Medicare Participation Announcement](http://www.cms.gov/medicare-participation)
        *   [Providers & suppliers](http://www.cms.gov/medicare/enrollment-renewal/providers-suppliers)
        *   [Medicare Managed Care Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/managed-care-eligibility-enrollment)
        *   [Part D Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/part-d-enrollment-elig […]

— `Medicare.gov coverage pages` §CMS.gov main menu ¶19

### c3 (optional)

Part B DME cost sharing is generally 20% coinsurance after the deductible

> *   [Part A cost report audit](http://www.cms.gov/medicare/audits-compliance/part-a-cost-report)
        *   [Part C/Part D compliance & audits](http://www.cms.gov/medicare/audits-compliance/part-c-d)

— `Medicare.gov coverage pages` §CMS.gov main menu ¶52

> *   [Original Medicare (Part A and B) Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/original-part-a-b)
        *   [Annual Medicare Participation Announcement](http://www.cms.gov/medicare-participation)
        *   [Providers & suppliers](http://www.cms.gov/medicare/enrollment-renewal/providers-suppliers)
        *   [Medicare Managed Care Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/managed-care-eligibility-enrollment)
        *   [Part D Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/part-d-enrollment-elig […]

— `Medicare.gov coverage pages` §CMS.gov main menu ¶19

> Back to  menu
### What is Medicaid?

— `Medicare.gov coverage pages` §CMS.gov main menu ¶68

## Required evidence key phrases

### e1 (**must**) — Medicare.gov CGM coverage page [Fact sheet]

`Part B`

> *   [Original Medicare (Part A and B) Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/original-part-a-b)
        *   [Annual Medicare Participation Announcement](http://www.cms.gov/medicare-participation)
        *   [Providers & suppliers](http://www.cms.gov/medicare/enrollment-renewal/providers-suppliers)
        *   [Medicare Managed Care Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/managed-care-eligibility-enrollment)
        *   [Part D Eligibility and Enrollment](http://www.cms.gov/medicare/enrollment-renewal/part-d-enrollment-elig […]

— `Medicare.gov coverage pages` §CMS.gov main menu ¶19

> *   [Part A cost report audit](http://www.cms.gov/medicare/audits-compliance/part-a-cost-report)
        *   [Part C/Part D compliance & audits](http://www.cms.gov/medicare/audits-compliance/part-c-d)

— `Medicare.gov coverage pages` §CMS.gov main menu ¶52

> *   [Original Medicare appeals](http://www.cms.gov/medicare/appeals-grievances/fee-for-service)
        *   [Managed Care appeals & grievances](http://www.cms.gov/medicare/appeals-grievances/managed-care)
        *   [Medicare Prescription drug appeals & grievances](http://www.cms.gov/medicare/appeals-grievances/prescription-drug)
        *   [Ombudsman Center](http://www.cms.gov/medicare/appeals-grievances/ombudsman-center)
        *   [Appeals Decision Search (Part C & Part D)](http://www.cms.gov/medicare/appeals-grievances/appeals-decision-search-part-c-d)

— `Medicare.gov coverage pages` §CMS.gov main menu ¶37

`durable medical equipment`

> *   [About Open Door Forums](http://www.cms.gov/training-education/open-door-forums/about)
        *   [Ambulance](http://www.cms.gov/training-education/open-door-forums/ambulance "The Ambulance Open Door Forum (ODF) addresses issues related to the payment, billing, coverage and delivery of services in the ambulance industry.")
        *   [End-Stage Renal Disease (ESRD) Dialysis Facility Care Compare](http://www.cms.gov/training-education/cms-open-door-forums/end-stage-renal-disease-esrd-dialysis-facility-care-compare)
        *   [Home Health, Hospice & Durable Medical Equipment (DME)](http: […]

— `Medicare.gov coverage pages` §CMS.gov main menu ¶195

> *   [Emergency Room Rights](http://www.cms.gov/priorities/your-patient-rights/emergency-room-rights)
        *   [Medical bill rights](http://www.cms.gov/medical-bill-rights)

— `Medicare.gov coverage pages` §CMS.gov main menu ¶181

> *   [Plan payment](http://www.cms.gov/medicare/health-drug-plans/plan-payment)
        *   [Plan payment data](http://www.cms.gov/medicare/health-drug-plans/plan-payment-data)
        *   [Medical loss ratio](http://www.cms.gov/medicare/health-drug-plans/medical-loss-ratio)
        *   [Managed care marketing](http://www.cms.gov/medicare/health-drug-plans/managed-care-marketing)
        *   [Medicare Advantage application](http://www.cms.gov/medicare/health-drug-plans/medicare-advantage-application)
        *   [Medigap (Medicare supplement health insurance)](http://www.cms.gov/medicare/health […]

— `Medicare.gov coverage pages` §CMS.gov main menu ¶58
