"""The evidence model (docs/04).

`store.py` creates evidence and enforces the docs/04 §3 rules — above all that a
passage is verbatim, which is the property the whole project rests on. `graph.py`
turns evidence into claims with statuses, contradictions and supersession edges.
`cite.py` renders citations from document metadata, omitting what it does not know.
"""

from prime_search.evidence.cite import build_citations, citation_label
from prime_search.evidence.graph import ClaimGraph, build_claim_graph, supersession_edges
from prime_search.evidence.store import EvidenceRejected, EvidenceStore

__all__ = [
    "ClaimGraph",
    "EvidenceRejected",
    "EvidenceStore",
    "build_citations",
    "build_claim_graph",
    "citation_label",
    "supersession_edges",
]
