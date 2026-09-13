"""Source tiers, domain rules and URL identity (docs/04 §1, docs/01 §5).

One table, matched longest-host-then-longest-path, because a single host serves
several tiers: `cms.gov/medicare-coverage-database` is the operative rule while the
rest of cms.gov is fact sheets and newsroom items, and docs/04 §1 makes fda.gov
primary only for "labels and approvals". Host-only classification would score a CMS
press release 1.0.

docs/04 §1 names organizations, never hostnames, so every host below is researched
rather than specified. Keeping them as data means a wrong guess is a one-line fix
plus a test row, not a code change (docs/11 decision log).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal, get_args
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

Tier = Literal[
    "primary_policy", "official_secondary", "professional", "trade", "web", "unknown"
]

# docs/04 §1, verbatim.
SOURCE_QUALITY: dict[Tier, float] = {
    "primary_policy": 1.0,
    "official_secondary": 0.85,
    "professional": 0.7,
    "trade": 0.5,
    "web": 0.3,
    "unknown": 0.3,
}

# docs/05 §2 needs "tier >= official_secondary" as a single test
# (`primary_source_ratio`), and docs/04 §1 gives web and unknown the same 0.3, so
# quality cannot be the sort key. `unknown` sorts below `web` because it is an
# absence of evidence about the source, not a judgment about it.
TIER_RANK: dict[Tier, int] = {
    "unknown": 0,
    "web": 1,
    "trade": 2,
    "professional": 3,
    "official_secondary": 4,
    "primary_policy": 5,
}


@dataclass(frozen=True, slots=True)
class SourceRule:
    host: str  # matches the host itself and any subdomain
    path_prefix: str  # "/" matches everything
    tier: Tier
    publisher: str | None = None


# Longest host suffix wins, then longest path prefix; the order here is irrelevant.
RULES: tuple[SourceRule, ...] = (
    # --- primary_policy: the document that *is* the rule (docs/04 §1) ----------
    SourceRule("cms.gov", "/medicare-coverage-database", "primary_policy", "CMS"),
    SourceRule("innovation.cms.gov", "/", "primary_policy", "CMS Innovation Center"),
    SourceRule("federalregister.gov", "/", "primary_policy", "Federal Register"),
    SourceRule("govinfo.gov", "/", "primary_policy", "U.S. GPO"),
    SourceRule("ecfr.gov", "/", "primary_policy", "eCFR"),
    # The Social Security Act itself, which is where Part D's statutory exclusions live
    # (1860D-2(e)(2) -> 1927(d)(2)) — two SearchBench records name 1927(d)(2)(A) as
    # their governing document and the compilation on ssa.gov is the operative text.
    #
    # This classifies the host; it deliberately does NOT reach `PRIMARY_DOMAINS` below,
    # which docs/01 §5 pins and every production search uses as its `include_domains`.
    # A document found on ssa.gov weighs what the statute weighs; where the agent is
    # told to look is a separate decision, and not one this rule should make.
    SourceRule("ssa.gov", "/OP_Home", "primary_policy", "SSA"),
    SourceRule("ssa.gov", "/", "official_secondary", "SSA"),
    # FDA: primary only where the page *is* the approval, clearance or label record.
    SourceRule("accessdata.fda.gov", "/", "primary_policy", "FDA"),
    SourceRule("dailymed.nlm.nih.gov", "/", "primary_policy", "NLM DailyMed"),
    # MAC sites. docs/04 §1 names the contractors; these are their hostnames.
    SourceRule("noridianmedicare.com", "/", "primary_policy", "Noridian"),
    SourceRule("cgsmedicare.com", "/", "primary_policy", "CGS"),
    SourceRule("palmettogba.com", "/", "primary_policy", "Palmetto GBA"),
    SourceRule("ngsmedicare.com", "/", "primary_policy", "National Government Services"),
    SourceRule("wpsgha.com", "/", "primary_policy", "WPS GHA"),
    SourceRule("novitas-solutions.com", "/", "primary_policy", "Novitas Solutions"),
    SourceRule("fcso.com", "/", "primary_policy", "First Coast Service Options"),
    # --- official_secondary: official but not the operative text ---------------
    SourceRule("cms.gov", "/", "official_secondary", "CMS"),
    SourceRule("medicare.gov", "/", "official_secondary", "Medicare.gov"),
    SourceRule("fda.gov", "/", "official_secondary", "FDA"),
    SourceRule("hhs.gov", "/", "official_secondary", "HHS"),
    SourceRule("oig.hhs.gov", "/", "official_secondary", "HHS OIG"),
    SourceRule("whitehouse.gov", "/", "official_secondary", "The White House"),
    SourceRule("medpac.gov", "/", "official_secondary", "MedPAC"),
    # --- professional: authoritative on practice, not on coverage -------------
    SourceRule("diabetesjournals.org", "/", "professional", "American Diabetes Association"),
    SourceRule("diabetes.org", "/", "professional", "American Diabetes Association"),
    SourceRule("aace.com", "/", "professional", "AACE"),
    SourceRule("endocrine.org", "/", "professional", "Endocrine Society"),
    SourceRule("ahrq.gov", "/", "professional", "AHRQ"),
    SourceRule("kff.org", "/", "professional", "KFF"),
    SourceRule("healthaffairs.org", "/", "professional", "Health Affairs"),
    SourceRule("nejm.org", "/", "professional", "NEJM"),
    SourceRule("jamanetwork.com", "/", "professional", "JAMA Network"),
    SourceRule("pubmed.ncbi.nlm.nih.gov", "/", "professional", "PubMed"),
    SourceRule("medicareinteractive.org", "/", "professional", "Medicare Rights Center"),
    # --- trade: useful for change detection; must point at a primary source ---
    SourceRule("fiercehealthcare.com", "/", "trade", "Fierce Healthcare"),
    SourceRule("statnews.com", "/", "trade", "STAT"),
    SourceRule("healthcaredive.com", "/", "trade", "Healthcare Dive"),
    SourceRule("medtechdive.com", "/", "trade", "MedTech Dive"),
    SourceRule("modernhealthcare.com", "/", "trade", "Modern Healthcare"),
    SourceRule("ajmc.com", "/", "trade", "AJMC"),
    SourceRule("hmenews.com", "/", "trade", "HME News"),
    SourceRule("endpts.com", "/", "trade", "Endpoints News"),
    SourceRule("jdsupra.com", "/", "trade", None),  # law-firm client alerts
    SourceRule("natlawreview.com", "/", "trade", None),
    SourceRule("lexology.com", "/", "trade", None),
    SourceRule("law360.com", "/", "trade", None),
    # --- web: never sole support for a coverage claim -------------------------
    SourceRule("dexcom.com", "/", "web", "Dexcom"),
    SourceRule("abbott.com", "/", "web", "Abbott"),
    SourceRule("freestyle.abbott", "/", "web", "Abbott"),
    SourceRule("medtronicdiabetes.com", "/", "web", "Medtronic"),
    SourceRule("novonordisk.com", "/", "web", "Novo Nordisk"),
    SourceRule("novocare.com", "/", "web", "Novo Nordisk"),
    SourceRule("lilly.com", "/", "web", "Eli Lilly"),
    SourceRule("goodrx.com", "/", "web", "GoodRx"),
    SourceRule("healthline.com", "/", "web", "Healthline"),
    SourceRule("webmd.com", "/", "web", "WebMD"),
    SourceRule("reddit.com", "/", "web", None),
)

# Hosts allowed to *hold* the operative text. Post-fetch promotion is limited to
# these, so a vendor page quoting "LCD L33822" cannot become primary_policy.
_OFFICIAL_HOSTS: frozenset[str] = frozenset(
    rule.host for rule in RULES if TIER_RANK[rule.tier] >= TIER_RANK["official_secondary"]
)

# Doc types that are official commentary even when served from a primary path.
_SECONDARY_DOC_TYPES = frozenset({"Fact sheet", "Press release", "MLN Matters"})
# Doc types that are the rule itself (docs/04 §2).
_PRIMARY_DOC_TYPES = frozenset({"LCD", "Article", "NCD", "Label", "Approval", "510(k)"})
# The subset docs/04 §1 calls out for FDA, and the hosts that serve them.
_FDA_DOC_TYPES = frozenset({"Label", "Approval", "510(k)"})
_FDA_HOSTS = frozenset({"fda.gov", "accessdata.fda.gov", "dailymed.nlm.nih.gov"})

# Query parameters that change navigation, not identity (docs/03 §13). `ver` is
# deliberately kept: a different LCD version is a different document, and docs/04
# §4's supersession edges compare versions of the same external id.
_DROP_PARAMS = frozenset(
    {
        "bc", "keyword", "keywordtype", "keywordlookup", "areaid", "doctype",
        "docstatus", "contractorname", "cntrctr", "sortby", "from", "from2",
        "fbclid", "gclid", "_ga", "mc_cid", "mc_eid", "ref", "source",
    }
)


def normalize_url(url: str) -> str:
    """Canonical form used for `doc_id` and for cache keys (docs/03 §13).

    Scheme is forced to https and `www.` dropped so http/https and www/non-www
    duplicates collapse. Parameter *names* are lowercased because the CMS coverage
    database emits both `articleId` and `articleid` for the same page (observed
    2026-09-12); values keep their case, since `ApplNo=209637` and
    `event=overview.process` are meaningful to FDA's CGI.
    """
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    query = sorted(
        (key.lower(), value)
        for key, value in parse_qsl(parts.query)
        if key.lower() not in _DROP_PARAMS and not key.lower().startswith("utm_")
    )
    return urlunsplit(("https", host, path, urlencode(query), ""))


def host_of(url: str) -> str:
    return (urlsplit(url.strip()).hostname or "").lower().removeprefix("www.")


def doc_id_for(url: str) -> str:
    """docs/02 §2.4's `"doc_" + sha1(url)[:10]`, taken over the normalized URL
    (docs/03 §13), so two agents reaching the same page by different links share
    one document."""
    digest = hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()
    return f"doc_{digest[:10]}"


def _host_matches(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith(f".{suffix}")


def _best_rule(url: str) -> SourceRule | None:
    host, path = host_of(url), (urlsplit(url).path or "/").lower()
    matches = [
        rule
        for rule in RULES
        if _host_matches(host, rule.host) and path.startswith(rule.path_prefix.lower())
    ]
    if not matches:
        return None
    # Longest host suffix first (accessdata.fda.gov beats fda.gov), then longest
    # path prefix (/medicare-coverage-database beats /).
    return max(matches, key=lambda rule: (len(rule.host), len(rule.path_prefix)))


def classify(url: str) -> tuple[Tier, str | None]:
    """Tier and publisher at document creation, from the URL alone (docs/04 §1)."""
    rule = _best_rule(url)
    return ("unknown", None) if rule is None else (rule.tier, rule.publisher)


def tier_for(url: str) -> Tier:
    return classify(url)[0]


def quality(tier: Tier) -> float:
    """docs/04 §3 rule 6: an evidence item's `source_quality` is copied from here."""
    return SOURCE_QUALITY[tier]


def tier_rank(tier: Tier) -> int:
    return TIER_RANK[tier]


def at_least(tier: Tier, floor: Tier = "official_secondary") -> bool:
    """docs/04 §1's consumer rule and docs/05's `primary_source_ratio` in one call."""
    return TIER_RANK[tier] >= TIER_RANK[floor]


def refine_tier(
    url: str,
    url_tier: Tier,
    *,
    doc_type: str | None,
    document_id_external: str | None,
) -> Tier:
    """docs/04 §1: "refined after fetch from the document's own metadata".

    The spec requires the refinement but defines no algorithm; these rules are
    this build's (docs/11 decision log). Two directions only:

    * promote when the fetched text proves the page *is* the rule — an LCD, Article,
      NCD or FDA record carrying its own external id — and the host is official. A
      Dexcom page quoting "LCD L33822" stays `web`.
    * demote a primary URL whose content turns out to be commentary (a fact sheet or
      press release served from a primary path).

    Never below the URL tier: a MAC page whose text extracted badly is still the MAC.
    """
    if doc_type in _SECONDARY_DOC_TYPES and url_tier == "primary_policy":
        return "official_secondary"
    host = host_of(url)
    if not any(_host_matches(host, official) for official in _OFFICIAL_HOSTS):
        return url_tier
    if doc_type in _PRIMARY_DOC_TYPES and document_id_external:
        return "primary_policy"
    # docs/04 §1 makes "fda.gov labels and approvals" primary_policy. A label page
    # often states no application number at all, so requiring an external id here
    # would leave every FDA label stuck at official_secondary.
    if doc_type in _FDA_DOC_TYPES and any(
        _host_matches(host, fda_host) for fda_host in _FDA_HOSTS
    ):
        return "primary_policy"
    return url_tier


def domains_for(*tiers: Tier) -> list[str]:
    """`include_domains` values for a set of tiers (docs/01 §5). Tavily matches
    subdomains, so the registrable hosts are enough."""
    wanted = set(tiers)
    return sorted({rule.host for rule in RULES if rule.tier in wanted})


# docs/01 §5's "domain allow-list for primary source filtering": cms.gov, *.cms.gov,
# MAC domains, fda.gov. Replaces the 1.2 placeholder ["cms.gov", "fda.gov"], which
# omitted every MAC.
#
# `fda.gov` is named by §5 and belongs here even though the host's *tier* is
# official_secondary: an include-domain list says where to look, while the tier says
# how much a document weighs. Excluding it would make FDA labels — which docs/04 §1
# calls primary — unreachable by a primary-filtered search.
# `ssa.gov` is excluded: the rule above classifies the statute correctly, but §5's list
# is cms.gov + MACs + fda.gov and a caller that wants the Act asks for it explicitly
# (`eval/searchbench/fetch_sources.py` does).
PRIMARY_DOMAINS: list[str] = sorted(
    {*domains_for("primary_policy"), "fda.gov"} - {"ssa.gov"}
)
OFFICIAL_DOMAINS: list[str] = domains_for("primary_policy", "official_secondary")

# The three tables must stay in step; a new tier without a rank breaks at_least().
assert set(get_args(Tier)) == set(SOURCE_QUALITY) == set(TIER_RANK)
