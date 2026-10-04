"""Shared helpers for ingest tests: recorded fixtures and a fake HTTP transport."""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from atlas.ingest.common import PoliteClient
from atlas.models.evidence import Edge, Node, NodeType

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"

ID_PATTERNS: dict[NodeType, str] = {
    NodeType.DISEASE: r"^MONDO:\d{7}$",
    NodeType.GENE: r"^HGNC:\d+$",
    NodeType.PHENOTYPE: r"^HP:\d{7}$",
    NodeType.MECHANISM: r"^GO:\d{7}$",
    NodeType.STUDY: r"^clinicaltrials:NCT\d{8}$",
    NodeType.PUBLICATION: r"^PMID:\d+$",
    NodeType.PATIENT_GROUP: r"^org:[a-z0-9-]+$",
    NodeType.FUNDER: r"^org:[a-z0-9-]+$",
    NodeType.ASSET: r"^asset:[a-z0-9-]+$",
}


def load_fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return data


def fake_client(handler: Callable[[httpx.Request], httpx.Response]) -> PoliteClient:
    """A PoliteClient that never sleeps and answers from ``handler``."""
    return PoliteClient(
        min_interval_s=0.0,
        retries=1,
        backoff_s=0.0,
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )


def assert_valid_ids(nodes: tuple[Node, ...]) -> None:
    for node in nodes:
        pattern = ID_PATTERNS.get(node.type)
        if pattern is not None:
            assert re.match(pattern, node.id), f"{node.type}: bad id {node.id}"


def assert_provenance(edges: tuple[Edge, ...], extractor: str) -> None:
    for edge in edges:
        assert edge.provenance.url is not None
        assert str(edge.provenance.url).startswith("https://")
        assert edge.provenance.extractor == extractor
        assert edge.provenance.source_record_id
        assert edge.provenance.retrieved_at.tzinfo is not None
        # Round-trip through JSON keeps the deterministic id.
        assert Edge.model_validate(edge.model_dump(mode="json")).id == edge.id


def assert_sorted_unique(nodes: tuple[Node, ...], edges: tuple[Edge, ...]) -> None:
    ids = [node.id for node in nodes]
    assert ids == sorted(set(ids))
    edge_ids = [edge.id for edge in edges]
    assert len(edge_ids) == len(set(edge_ids))
    keys = [(e.source_id, e.relation.value, e.target_id, e.id) for e in edges]
    assert keys == sorted(keys)
