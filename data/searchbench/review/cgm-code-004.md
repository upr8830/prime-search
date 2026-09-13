# cgm-code-004 — validation worksheet

**If a Medicare beneficiary reads their CGM on a smartphone instead of a dedicated receiver, are the supplies still covered?**

`cgm` · tier 3 · coding · split `holdout`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Draft summary

Coverage of supplies is tied to a covered durable receiver in the DME benefit; the policy article addresses the use of a smartphone/app as a display. Answer must cite the current article language on receivers and smartphone use rather than vendor pages.

## Governing documents

- `A52464` via **record_url** — [Glucose Monitor - Policy Article (A52464) - CMS](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464) · primary_policy · 2025-02-18 · 281 paragraphs

## Required claims, against the live text

### c1 (**must**)

The DME benefit requires a covered CGM receiver; the article addresses smartphone display use

> A non-adjunctive CGM can be used to make treatment decisions without the need for a stand-alone BGM to confirm testing results. An adjunctive CGM requires the user verify their glucose levels or trends displayed on a CGM with a BGM prior to making treatment decisions. On February 28, 2022, CMS determined that both non-adjunctive and adjunctive CGMs may be classified as DME. CGM devices that solely display results on a smartphone and do not have a stand-alone receiver or integration into an insulin infusion pump do not meet the definition of DME and will be denied as non-covered (no benefit).

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶32

> If a beneficiary never uses a DME receiver or insulin infusion pump to display CGM glucose data, the supply allowance is not covered by Medicare.

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶38

> Coverage of a CGM system supply allowance (code A4238 or A4239) is available for CGM systems when the beneficiary uses a stand-alone receiver or insulin infusion pump classified as DME to display glucose data. In addition, Medicare coverage is available for a CGM system supply allowance if a non-DME device (watch, smartphone, tablet, laptop computer, etc.) is used in conjunction with the durable CGM receiver (code E2102 or E2103). The following are examples of this provision:

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶35

### c2 (optional)

Vendor pages are not authoritative for coverage

> Alcohol or peroxide (codes A4244, A4245), betadine or hexachlorophene (pHisohex) (codes A4246, A4247) are non-covered since these items are not required for the proper functioning of the device.

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶41

> Smart devices are non-covered by Medicare because they do not meet the definition of DME (i.e., not primarily medical in nature and are useful in the absence of illness). Claims for smart devices must be billed using code A9270 (non-covered item or service).

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶39

> Reflectance colorimeter devices used for measuring blood glucose levels in clinical settings are not covered as durable medical equipment for use in the home because their need for frequent professional re-calibration makes them unsuitable for home use.

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶43

## Required evidence key phrases

### e1 (**must**) — A52464 [Article]

`smartphone`

> Coverage of a CGM system supply allowance (code A4238 or A4239) is available for CGM systems when the beneficiary uses a stand-alone receiver or insulin infusion pump classified as DME to display glucose data. In addition, Medicare coverage is available for a CGM system supply allowance if a non-DME device (watch, smartphone, tablet, laptop computer, etc.) is used in conjunction with the durable CGM receiver (code E2102 or E2103). The following are examples of this provision:

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶35

> A non-adjunctive CGM can be used to make treatment decisions without the need for a stand-alone BGM to confirm testing results. An adjunctive CGM requires the user verify their glucose levels or trends displayed on a CGM with a BGM prior to making treatment decisions. On February 28, 2022, CMS determined that both non-adjunctive and adjunctive CGMs may be classified as DME. CGM devices that solely display results on a smartphone and do not have a stand-alone receiver or integration into an insulin infusion pump do not meet the definition of DME and will be denied as non-covered (no benefit).

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶32

> Revision Effective Date: 02/28/2022
NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES:
Removed: Reference to CMS Ruling 1682R
Removed: "therapeutic" from the DME benefit statement
Added: Information regarding classification of CGMs as DME
Added: "CGM devices that solely display results on a smartphone and do not have a stand-alone receiver or integration into an insulin infusion pump do not meet the definition of DME and will be denied as non-covered (no benefit)."
Added: Supply allowance HCPCS code A4238 to billing information
Added: HCPCS codes A4238 and E2102 to supply allowance statements
R […]

— `A52464` §Revision History Information ¶159

`receiver`

> Medicare coverage of a CGM supply allowance is available when a beneficiary uses a durable CGM receiver to display their glucose data and also transmits that data to a caregiver through a smart phone or other non-DME receiver.

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶36

> Coverage of a CGM system supply allowance (code A4238 or A4239) is available for CGM systems when the beneficiary uses a stand-alone receiver or insulin infusion pump classified as DME to display glucose data. In addition, Medicare coverage is available for a CGM system supply allowance if a non-DME device (watch, smartphone, tablet, laptop computer, etc.) is used in conjunction with the durable CGM receiver (code E2102 or E2103). The following are examples of this provision:

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶35

> If a beneficiary never uses a DME receiver or insulin infusion pump to display CGM glucose data, the supply allowance is not covered by Medicare.

— `A52464` §NON-MEDICAL NECESSITY COVERAGE AND PAYMENT RULES ¶38
