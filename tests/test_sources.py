"""Source tiers and URL identity (docs/04 §1, docs/03 §13).

The URL table is docs/09 §1.3's required test. Every row is a precedence trap rather
than a spot check: cms.gov serves two tiers, fda.gov is primary only for approvals
and labels, and the MAC hostnames are researched rather than specified — so a wrong
guess has to fail here and nowhere else.
"""

from __future__ import annotations

from typing import get_args

import pytest

from prime_search.primitives import sources
from prime_search.schemas import Document

CASES: list[tuple[str, str]] = [
    # cms.gov: the coverage database is the rule; the rest of the site is commentary.
    ("https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822", "primary_policy"),
    (
        "https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464",
        "primary_policy",
    ),
    ("https://www.cms.gov/newsroom/fact-sheets/continuous-glucose-monitors", "official_secondary"),
    ("https://www.cms.gov/files/document/mm13361-glucose-monitors.pdf", "official_secondary"),
    ("https://www.cms.gov/newsroom/press-releases/cms-finalizes-dmepos-rule", "official_secondary"),
    ("https://innovation.cms.gov/innovation-models/gdmi", "primary_policy"),
    ("https://www.medicare.gov/coverage/continuous-glucose-monitors", "official_secondary"),
    (
        "https://www.federalregister.gov/documents/2023/11/06/2023-23773/medicare-program",
        "primary_policy",
    ),
    ("https://www.govinfo.gov/content/pkg/CFR-2024-title42-vol3/sec414-210.htm", "primary_policy"),
    # MAC hosts, including a subdomain and a www-less host.
    ("https://med.noridianmedicare.com/web/jddme/policies/dme-lcds", "primary_policy"),
    ("https://www.cgsmedicare.com/jc/pubs/news/2025/cgm-billing.html", "primary_policy"),
    ("https://www.palmettogba.com/palmetto/jma.nsf/DID/CGM", "primary_policy"),
    # fda.gov: the clearance record is primary, the newsroom is not.
    (
        "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K213919",
        "primary_policy",
    ),
    ("https://www.fda.gov/news-events/press-announcements/fda-clears-cgm", "official_secondary"),
    (
        "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=adec4fd2-6858-4c99-91d4",
        "primary_policy",
    ),
    ("https://diabetesjournals.org/care/article/48/Supplement_1/S1/1234", "professional"),
    ("https://www.kff.org/medicare/issue-brief/glp-1-coverage", "professional"),
    ("https://www.fiercehealthcare.com/payers/cms-expands-cgm-coverage", "trade"),
    ("https://www.jdsupra.com/legalnews/cms-cgm-policy-update-1234567/", "trade"),
    ("https://www.dexcom.com/en-us/medicare-coverage", "web"),
    ("https://someclinicblog.example/2025/cgm-and-medicare", "unknown"),
]


@pytest.mark.parametrize(("url", "expected"), CASES)
def test_tier_classification(url: str, expected: str) -> None:
    assert sources.tier_for(url) == expected


def test_quality_table_matches_spec() -> None:
    """docs/04 §1's table, verbatim. docs/04 §3 rule 6 copies these onto evidence."""
    assert sources.SOURCE_QUALITY == {
        "primary_policy": 1.0,
        "official_secondary": 0.85,
        "professional": 0.7,
        "trade": 0.5,
        "web": 0.3,
        "unknown": 0.3,
    }


def test_tier_rank_is_a_total_order_even_where_quality_ties() -> None:
    """docs/05 needs "tier >= official_secondary" as one comparison, but web and
    unknown share 0.3, so quality cannot be the sort key."""
    ranks = [sources.TIER_RANK[tier] for tier in get_args(sources.Tier)]
    assert len(set(ranks)) == len(ranks)
    assert sources.TIER_RANK["unknown"] < sources.TIER_RANK["web"]
    assert sources.quality("web") == sources.quality("unknown")
    assert all(sources.at_least(tier) for tier in ("primary_policy", "official_secondary"))
    assert not any(
        sources.at_least(tier) for tier in ("professional", "trade", "web", "unknown")
    )


def test_document_tier_literal_matches_the_sources_literal() -> None:
    """schemas.py spells the six tiers inline to stay docs/02-exact; this keeps the
    two spellings from drifting apart."""
    field = Document.model_fields["source_tier"]
    assert set(get_args(field.annotation)) == set(get_args(sources.Tier))


def test_primary_domains_covers_every_host_docs_01_5_names() -> None:
    """docs/01 §5's allow-list is "cms.gov, *.cms.gov, MAC domains, fda.gov".

    fda.gov belongs here even though its *tier* is official_secondary: an
    include-domain list says where to look, the tier says how much a document
    weighs. Leaving it out made FDA labels — primary per docs/04 §1 — unreachable
    by a primary-filtered search.
    """
    assert sources.PRIMARY_DOMAINS != ["cms.gov", "fda.gov"]  # the 1.2 placeholder
    for host in (
        "cms.gov",
        "fda.gov",
        "accessdata.fda.gov",
        "noridianmedicare.com",
        "cgsmedicare.com",
        "palmettogba.com",
        "ngsmedicare.com",
        "wpsgha.com",
        "novitas-solutions.com",
        "fcso.com",
    ):
        assert host in sources.PRIMARY_DOMAINS


def test_an_fda_label_reaches_primary_policy_after_fetch() -> None:
    """docs/04 §1: "fda.gov labels and approvals" are primary_policy. A label page
    often states no application number, so promotion cannot require an external id."""
    assert (
        sources.refine_tier(
            "https://www.fda.gov/drugs/postmarket-drug-safety/ozempic-label",
            "official_secondary",
            doc_type="Label",
            document_id_external=None,
        )
        == "primary_policy"
    )
    # A non-FDA host does not get that exemption.
    assert (
        sources.refine_tier(
            "https://www.dexcom.com/label",
            "web",
            doc_type="Label",
            document_id_external=None,
        )
        == "web"
    )


@pytest.mark.parametrize(
    ("left", "right"),
    [
        # Observed live: the coverage database emits both spellings for one page.
        (
            "https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleId=52464",
            "https://cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464",
        ),
        (
            "http://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822",
            "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822#top",
        ),
        (
            "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822&bc=0",
            "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822&utm_source=x",
        ),
    ],
)
def test_doc_id_collapses_equivalent_urls(left: str, right: str) -> None:
    assert sources.doc_id_for(left) == sources.doc_id_for(right)
    assert sources.doc_id_for(left).startswith("doc_")
    assert len(sources.doc_id_for(left)) == len("doc_") + 10


def test_doc_id_keeps_distinct_versions_distinct() -> None:
    """`ver` selects a genuinely different document; docs/04 §4 builds supersession
    edges between versions of one external id."""
    base = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822"
    assert sources.doc_id_for(base) != sources.doc_id_for(f"{base}&ver=63")


def test_refine_tier_promotes_and_demotes_only_where_justified() -> None:
    """docs/04 §1 requires post-fetch refinement and defines no algorithm; these are
    the rules this build chose (docs/11 decision log)."""
    # An FDA clearance record proves itself primary.
    assert (
        sources.refine_tier(
            "https://www.fda.gov/medical-devices/510k/k213919",
            "official_secondary",
            doc_type="510(k)",
            document_id_external="K213919",
        )
        == "primary_policy"
    )
    # A fact sheet served from a primary path is still commentary.
    assert (
        sources.refine_tier(
            "https://www.cms.gov/medicare-coverage-database/view/mln.aspx?id=1",
            "primary_policy",
            doc_type="Fact sheet",
            document_id_external=None,
        )
        == "official_secondary"
    )
    # A vendor page quoting an LCD is not the LCD.
    assert (
        sources.refine_tier(
            "https://www.dexcom.com/medicare",
            "web",
            doc_type="LCD",
            document_id_external="L33822",
        )
        == "web"
    )
    # A MAC page that extracted badly is still the MAC: never demote below the URL.
    assert (
        sources.refine_tier(
            "https://med.noridianmedicare.com/web/jddme/policies",
            "primary_policy",
            doc_type=None,
            document_id_external=None,
        )
        == "primary_policy"
    )
