# chg-glp1-001 — validation worksheet

**What changed in Medicare coverage of GLP-1 medications during 2026?**

`glp1` · tier 3 · change_detection · split `holdout`

Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and `validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.

## Flags

- [authoring] docs/08 §4: a change-detection key must list the changes with dates, but asserts none
- [resolution] 'CMS 2026 announcements' has no canonical id; best search hit was https://www.federalregister.gov/index/2026/centers-for-medicare-medicaid-services (primary_policy) — confirm this is the governing document

## Draft summary

An ordered, dated list of 2026 changes from primary CMS/HHS/FDA sources (e.g., start of any obesity coverage pathway, Innovation Center model milestones, price-negotiation effects, label changes), each with its effective date and source. Secondary sources are acceptable only as pointers.

## Governing documents

- `CMS 2026 announcements` via **search** — [Federal Register :: 2026 Federal Register Index :: Centers for Medicare & Medicaid Services](https://www.federalregister.gov/index/2026/centers-for-medicare-medicaid-services) · primary_policy · no date found · 120 paragraphs

## Required claims, against the live text

### c1 (**must**)

Changes are listed in date order with effective dates

> Background and more details are available in the
*[Search & Navigation](/reader-aids/recent-updates/2024/10/combined-search-and-navigation-omni-box)*
guide.

— `CMS 2026 announcements` §2026 Federal Register Index ¶6

> ##### [Ensuring Safety through Domestic Security with Made in America Personal Protective Equipment and Essential Medicine Procurement by Medicare Participating Hospitals](#) 1

— `CMS 2026 announcements` §Ensuring Safety through Domestic Security with Made in America Personal Protective Equipment and Essential Medicine Procurement by Medicare Participating Hospitals 1 ¶42

> This index provides descriptive entries and Federal Register page numbers for documents published by Centers for Medicare & Medicaid Services in the daily Federal Register. It includes entries, with select metadata for all documents published in the 2026 calendar year.

— `CMS 2026 announcements` §Centers for Medicare & Medicaid Services ¶10

### c2 (**must**)

Each change cites a primary CMS/HHS/FDA source

> The documents posted on this site are XML renditions of published Federal
Register documents. Each document posted on the site includes a link to the
corresponding official PDF file on govinfo.gov. This prototype edition of the
daily Federal Register on FederalRegister.gov will remain an unofficial
informational resource until the Administrative Committee of the Federal
Register (ACFR) issues a regulation granting it official legal status.
For complete information about, and access to, our official publications
and services, go to
[About the Federal Register](https://www.archives.gov/federal-r […]

— `CMS 2026 announcements` ¶1

> ##### [Preserving Medicaid Funding for Vulnerable Populations - Closing a Health Care-Related Tax Loophole](#) 1

— `CMS 2026 announcements` §Preserving Medicaid Funding for Vulnerable Populations - Closing a Health Care-Related Tax Loophole 1 ¶15

> ##### [Application from a Hospital Requesting Waiver for Organ Procurement Service Area (High Point Regional Health)](#) 1

— `CMS 2026 announcements` §Application from a Hospital Requesting Waiver for Organ Procurement Service Area (High Point Regional Health) 1 ¶95

### c3 (**must**)

Future-dated items are distinguished from in-effect items

> Background and more details are available in the
*[Search & Navigation](/reader-aids/recent-updates/2024/10/combined-search-and-navigation-omni-box)*
guide.

— `CMS 2026 announcements` §2026 Federal Register Index ¶6

> ##### [Updates to the Master List of Items Potentially Subject to Face-to-Face Encounter and Written Order Prior to Delivery and/or Prior Authorization Requirements; etc.](#) 1

— `CMS 2026 announcements` §Updates to the Master List of Items Potentially Subject to Face-to-Face Encounter and Written Order Prior to Delivery and/or Prior Authorization Requirements; etc. 1 ¶28

> ##### [Updates to the Master List of Items Potentially Subject to Face to Face Encounter and Written Order Prior to Delivery and/or Prior Authorization Requirements; etc.](#) 1

— `CMS 2026 announcements` §Updates to the Master List of Items Potentially Subject to Face to Face Encounter and Written Order Prior to Delivery and/or Prior Authorization Requirements; etc. 1 ¶27

## Required evidence key phrases

### e1 (**must**) — CMS 2026 announcements [Press release]

`2026`

> # 2026 Federal Register Index

— `CMS 2026 announcements` §2026 Federal Register Index ¶3

> ##### [Quarterly Listing of Program Issuances - April through June 2026](#) 1

— `CMS 2026 announcements` §Quarterly Listing of Program Issuances - April through June 2026 1 ¶100

> ##### [Quarterly Listing of Program Issuances - January through March 2026](#) 1

— `CMS 2026 announcements` §Quarterly Listing of Program Issuances - January through March 2026 1 ¶101
