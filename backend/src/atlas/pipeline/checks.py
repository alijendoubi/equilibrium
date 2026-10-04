"""Story checks on a built snapshot: the hero path exists and the gap disease is a real gap.

Hero path (undirected hops, as the path view reads them):
Gaucher type 2/3 -> GBA1 -> late-onset PD (GBA1-PD) -> ASPro-PD (NCT05778617) -> a funder/org.
Gap: saposin C deficiency has a node, a cause and phenotypes, but no ``studies_condition`` edge
and no ``represents`` edge.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from atlas.ingest.seeds import GAP_DISEASE, HERO_DISEASES, HERO_GENE, PARTNER_DISEASE

HERO_TRIAL = "clinicaltrials:NCT05778617"
ORG_PREFIX = "org:"


def _links(edges: Sequence[Mapping[str, Any]], a: str, b: str) -> list[str]:
    return sorted(
        f"{e['relation']}:{e['id']}" for e in edges if {e["source_id"], e["target_id"]} == {a, b}
    )


def story_checks(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return the hops of the hero path and the gap facts; ``ok`` is True when both hold."""
    edges: Sequence[Mapping[str, Any]] = snapshot["edges"]
    node_ids = {node["id"] for node in snapshot["nodes"]}
    trial_orgs = sorted(
        {
            other
            for e in edges
            for other in (e["source_id"], e["target_id"])
            if HERO_TRIAL in (e["source_id"], e["target_id"]) and other.startswith(ORG_PREFIX)
        }
    )
    hops = {f"{hero} - {HERO_GENE}": _links(edges, hero, HERO_GENE) for hero in HERO_DISEASES}
    hops[f"{HERO_GENE} - {PARTNER_DISEASE}"] = _links(edges, HERO_GENE, PARTNER_DISEASE)
    hops[f"{PARTNER_DISEASE} - {HERO_TRIAL}"] = _links(edges, PARTNER_DISEASE, HERO_TRIAL)
    for org in trial_orgs:
        hops[f"{HERO_TRIAL} - {org}"] = _links(edges, HERO_TRIAL, org)
    gap_edges = [e for e in edges if GAP_DISEASE in (e["source_id"], e["target_id"])]
    gap: dict[str, Any] = {
        "node_present": GAP_DISEASE in node_ids,
        "caused_by": sorted({e["target_id"] for e in gap_edges if e["relation"] == "caused_by"}),
        "phenotypes": sum(1 for e in gap_edges if e["relation"] == "has_phenotype"),
        "studies": sorted(
            e["source_id"] for e in gap_edges if e["relation"] == "studies_condition"
        ),
        "patient_groups": sorted(
            e["source_id"] for e in gap_edges if e["relation"] == "represents"
        ),
    }
    hero_ok = bool(trial_orgs) and all(hops.values())
    gap_ok = (
        gap["node_present"]
        and bool(gap["caused_by"])
        and gap["phenotypes"] > 0
        and not gap["studies"]
        and not gap["patient_groups"]
    )
    return {
        "ok": hero_ok and gap_ok,
        "hero_path": hops,
        "hero_ok": hero_ok,
        "gap": gap,
        "gap_ok": gap_ok,
    }
