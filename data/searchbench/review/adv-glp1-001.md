# adv-glp1-001 — validation worksheet

**Medicare now covers Ozempic for weight loss, right?**

`glp1` · tier 4 · contradiction · split `train`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [resolution] 'FDA Ozempic label' has no canonical id; best search hit was https://www.accessdata.fda.gov/drugsatfda_docs/label/2022/209637s012lbl.pdf (primary_policy) — confirm this is the governing document
- [resolution] 'SSA 1927(d)(2)(A)' has no canonical id; best search hit was https://www.ssa.gov/OP_Home/ssact/title19/1927.htm (primary_policy) — confirm this is the governing document
- [forbidden] f1 could not be checked automatically (no quoted wording or code to match): "Medicare covers Ozempic for weight loss" — verify by hand

## Draft summary

Not as stated. Ozempic's FDA label is for type 2 diabetes (and related indications), not weight loss; Part D coverage for a weight-loss purpose is statutorily excluded. Wegovy (also semaglutide) may be covered for cardiovascular risk reduction, and 2025–2026 obesity-coverage changes apply to specific criteria and dates. The answer must separate product, indication, and coverage pathway.

## Governing documents

- `FDA Ozempic label` via **search** — [FDA HIGHLIGHTS OF PRESCRIBING INFORMATION](https://www.accessdata.fda.gov/drugsatfda_docs/label/2022/209637s012lbl.pdf) · primary_policy · 2022-10-01 · 1 paragraphs
- `SSA 1927(d)(2)(A)` via **search** — [Social Security Act §1927](https://www.ssa.gov/OP_Home/ssact/title19/1927.htm) · primary_policy · no date found · 453 paragraphs

## Required claims, against the live text

### c1 (**must**)

Ozempic is labeled for type 2 diabetes, not weight loss

> (A) Agents when
used for anorexia, weight loss, or weight gain.

— `SSA 1927(d)(2)(A)` §PAYMENT FOR COVERED OUTPATIENT DRUGS[[296]](#ft296 "Footnote #296") ¶208

> mediated, marked initial maternal body weight loss and reductions in body weight gain and food consumption coincided with the occurrence of sporadic abnormalities (vertebra, sternebra, ribs) at ≥0.075 mg/kg twice weekly (≥3X human exposure). In a pre- and postnatal development study in pregnant cynomolgus monkeys, subcutaneous doses of 0.015, 0.075, and 0.15 mg/kg twice weekly (0.3-, 2-, and 4-fold the MRHD) were administered from Gestation Day 16 to 140. Pharmacologically mediated marked initial maternal body weight loss and reductions in body weight gain and food consumption coincided with a […]

— `FDA Ozempic label` ¶0

> (I) The type
of facility or entity.

— `SSA 1927(d)(2)(A)` §PAYMENT FOR COVERED OUTPATIENT DRUGS[[296]](#ft296 "Footnote #296") ¶139

### c2 (**must**)

Part D excludes coverage for weight loss as the purpose

> (A) Agents when
used for anorexia, weight loss, or weight gain.

— `SSA 1927(d)(2)(A)` §PAYMENT FOR COVERED OUTPATIENT DRUGS[[296]](#ft296 "Footnote #296") ¶208

> (VI) any prices
charged which are negotiated by a prescription drug plan under part
D of title XVIII, by an MA-PD plan under part C of such title with
respect to covered part D drugs or by a qualified retiree prescription
drug plan (as defined in section 1860D-22(a)(2)) with respect to
such drugs on behalf of individuals entitled to benefits under part
A or enrolled under part B of such title, or any discounts provided
by manufacturers under the Medicare coverage gap discount program
under section 1860D-14A .

— `SSA 1927(d)(2)(A)` §PAYMENT FOR COVERED OUTPATIENT DRUGS[[296]](#ft296 "Footnote #296") ¶121

> (3)  Limiting
definition.-The term "covered outpatient
drug" does not include any drug, biological product, or insulin
provided as part of, or as incident to and in the same setting as,
any of the following (and for which payment may be made under this
title as part of payment for the following and not as direct reimbursement
for the drug):

— `SSA 1927(d)(2)(A)` §PAYMENT FOR COVERED OUTPATIENT DRUGS[[296]](#ft296 "Footnote #296") ¶361

### c3 (**must**)

Wegovy's CV indication and the 2025–2026 obesity pathway are distinct and have their own criteria/dates

> nal function and explain the associated signs and symptoms of renal impairment, as well as the possibility of dialysis as a medical intervention if acute kidney injury occurs [see Warnings and Precautions (5.6)]. Hypersensitivity Reactions Inform patients that serious hypersensitivity reactions have been reported during postmarketing use of OZEMPIC. Advise patients on the symptoms of hypersensitivity reactions and instruct them to stop taking OZEMPIC and seek medical advice promptly if such symptoms occur [see Warnings and Precautions (5.7)]. Acute Gallbladder Disease Inform patients of the po […]

— `FDA Ozempic label` ¶0

> (K) Agents when
used for the treatment of sexual or erectile dysfunction, unless such
agents are used to treat a condition, other than sexual or erectile
dysfunction, for which the agents have been approved by the Food and
Drug Administration.

— `SSA 1927(d)(2)(A)` §PAYMENT FOR COVERED OUTPATIENT DRUGS[[296]](#ft296 "Footnote #296") ¶218

> (C) A covered
outpatient drug may be excluded with respect to the treatment of a
specific disease or condition for an identified population (if any)
only if, based on the drug's labeling (or, in the case of a
drug the prescribed use of which is not approved under the Federal
Food, Drug, and Cosmetic Act[[325]](#ft325 "Footnote #325") but is a medically accepted indication,
based on information from the appropriate compendia described in subsection
(k)(6)), the excluded drug does not have a significant, clinically
meaningful therapeutic advantage in terms of safety, effectiveness,
or clinical o […]

— `SSA 1927(d)(2)(A)` §PAYMENT FOR COVERED OUTPATIENT DRUGS[[296]](#ft296 "Footnote #296") ¶223

## Required evidence key phrases

### e1 (**must**) — FDA Ozempic label [Label]

`type 2 diabetes`

> (I) The type
of facility or entity.

— `SSA 1927(d)(2)(A)` §PAYMENT FOR COVERED OUTPATIENT DRUGS[[296]](#ft296 "Footnote #296") ¶139

> (bb) would be
a covered entity described in section 340B(a)(4) of the Public Health
Service Act insofar as the entity described in such section provides
the same type of services to the same type of populations as a covered
entity described in such section provides, but does not receive funding
under a provision of law referred to in such section;

— `SSA 1927(d)(2)(A)` §PAYMENT FOR COVERED OUTPATIENT DRUGS[[296]](#ft296 "Footnote #296") ¶135

> [[322]](#ftn322 "Footnote reference #322")
P.L. 114-74, §602(a)(2)
Inserted subparagraph (C). Effective November 2, 2016.

— `SSA 1927(d)(2)(A)` §PAYMENT FOR COVERED OUTPATIENT DRUGS[[296]](#ft296 "Footnote #296") ¶420

## Forbidden claims

- **f1**: Medicare covers Ozempic for weight loss — _label and statute_
