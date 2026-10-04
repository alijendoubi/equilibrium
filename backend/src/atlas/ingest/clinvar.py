"""ClinVar pathogenic / likely-pathogenic variant counts per seed gene (NCBI E-utilities).

Only ``esearch`` counts are used (``retmax=0``); no variant records are stored. Counts are gene
attributes, not variant nodes. ``<SYMBOL>[gene]`` matches every ClinVar record that lists the
gene, including multi-gene copy-number records, so treat the numbers as an upper bound.

Rate limits: NCBI allows 3 requests/second without a key and 10 with ``NCBI_API_KEY``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from atlas.ingest.common import IngestResult, JsonDict, PoliteClient, make_meta, merge_nodes
from atlas.ingest.seeds import SEED_GENES
from atlas.models.evidence import FrozenStrMap, Node, NodeType

SOURCE = "clinvar"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
INTERVAL_NO_KEY_S = 0.4
INTERVAL_WITH_KEY_S = 0.12

QUERIES: dict[str, str] = {
    "total": "{symbol}[gene]",
    "pathogenic": "{symbol}[gene] AND clinsig_pathogenic[prop]",
    "likely_pathogenic": "{symbol}[gene] AND clinsig_likely_pathogenic[prop]",
    "pathogenic_or_likely_pathogenic": (
        "{symbol}[gene] AND (clinsig_pathogenic[prop] OR clinsig_likely_pathogenic[prop])"
    ),
}


def min_interval(api_key: str | None) -> float:
    return INTERVAL_WITH_KEY_S if api_key else INTERVAL_NO_KEY_S


def esearch_count(client: PoliteClient, term: str, api_key: str | None) -> int:
    params: dict[str, str] = {"db": "clinvar", "term": term, "retmode": "json", "retmax": "0"}
    if api_key:
        params["api_key"] = api_key
    data = client.get_json(f"{EUTILS}/esearch.fcgi", params=params)
    return int(data["esearchresult"]["count"])


def fetch(client: PoliteClient, api_key: str | None = None) -> JsonDict:
    """Count ClinVar records per seed gene for each query in ``QUERIES``."""
    info = client.get_json(f"{EUTILS}/einfo.fcgi", params={"db": "clinvar", "retmode": "json"})
    db_info = info["einforesult"]["dbinfo"][0]
    version = str(db_info.get("dbbuild") or db_info.get("lastupdate") or "") or None
    counts: dict[str, dict[str, int]] = {}
    for gene_id, symbol in sorted(SEED_GENES.items()):
        counts[gene_id] = {
            name: esearch_count(client, template.format(symbol=symbol), api_key)
            for name, template in QUERIES.items()
        }
    return {
        "meta": make_meta(f"{EUTILS}/esearch.fcgi", version),
        "queries": QUERIES,
        "symbols": dict(sorted(SEED_GENES.items())),
        "counts": counts,
    }


def normalize(payload: Mapping[str, Any]) -> IngestResult:
    """Gene nodes carrying ClinVar counts as attributes (merged with Monarch genes by id)."""
    meta = payload["meta"]
    symbols: Mapping[str, str] = payload.get("symbols") or SEED_GENES
    nodes: list[Node] = []
    for gene_id, counts in sorted((payload.get("counts") or {}).items()):
        symbol = symbols.get(gene_id, gene_id)
        attributes = {f"clinvar_{name}": str(value) for name, value in sorted(counts.items())}
        attributes["clinvar_url"] = f"https://www.ncbi.nlm.nih.gov/clinvar/?term={symbol}%5Bgene%5D"
        attributes["clinvar_version"] = str(meta.get("source_version") or "unknown")
        nodes.append(
            Node(
                id=gene_id,
                type=NodeType.GENE,
                label=symbol,
                attributes=FrozenStrMap(attributes),
            )
        )
    return IngestResult(
        source=SOURCE,
        source_version=meta.get("source_version"),
        retrieved_at=str(meta["retrieved_at"]),
        nodes=merge_nodes(nodes),
        edges=(),
        notes={"records": len(nodes), "caveat": "[gene] counts include multi-gene records"},
    )
