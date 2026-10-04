"""Shared ingest plumbing: HTTP client, cache files, node/edge merging."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from atlas.ingest.common import (
    USER_AGENT,
    FetchError,
    PoliteClient,
    clean_text,
    dedupe_edges,
    make_meta,
    merge_nodes,
    read_cache,
    utc_now_iso,
    write_cache,
)
from atlas.models.evidence import Edge, EvidenceType, Node, NodeType, Provenance, Relation
from tests._ingest_helpers import fake_client


def test_client_sends_user_agent_and_returns_json() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    with fake_client(handler) as client:
        assert client.get_json("https://example.org/x", params={"a": "1"}) == {"ok": True}
    assert seen[0].headers["User-Agent"] == USER_AGENT
    assert "equilibrium" in USER_AGENT
    assert seen[0].url.params["a"] == "1"


def test_client_retries_transient_errors_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=[1])

    with fake_client(handler) as client:
        assert client.get_json("https://example.org/x") == [1]
    assert calls["n"] == 2


def test_client_retries_transport_errors_and_gives_up() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with fake_client(handler) as client, pytest.raises(FetchError, match="ConnectError"):
        client.get("https://example.org/x")


def test_client_gives_up_on_repeated_429() -> None:
    with (
        fake_client(lambda request: httpx.Response(429)) as client,
        pytest.raises(FetchError, match="HTTP 429"),
    ):
        client.get("https://example.org/x")


def test_client_raises_on_client_errors_without_retry() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    with fake_client(handler) as client, pytest.raises(httpx.HTTPStatusError):
        client.get("https://example.org/missing")
    assert calls["n"] == 1


def test_client_throttles_between_requests() -> None:
    sleeps: list[float] = []
    client = PoliteClient(
        min_interval_s=10.0,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        sleep=sleeps.append,
    )
    client.get("https://example.org/1")
    client.get("https://example.org/2")
    client.close()
    assert sleeps and sleeps[-1] > 9.0


def test_cache_round_trip_is_deterministic(tmp_path: Path) -> None:
    payload = {"b": [2, 1], "a": {"z": 1, "y": "é"}}
    path = write_cache(payload, "src", "payload", tmp_path)
    first = path.read_bytes()
    write_cache(payload, "src", "payload", tmp_path)
    assert path.read_bytes() == first
    assert first.index(b'"a"') < first.index(b'"b"')
    assert read_cache("src", "payload", tmp_path) == payload


def test_read_cache_missing_file_explains(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="online build"):
        read_cache("nope", "payload", tmp_path)


def test_make_meta_and_time_format() -> None:
    meta = make_meta("https://example.org", "v1", "2026-10-04T00:00:00Z")
    assert meta == {
        "url": "https://example.org",
        "source_version": "v1",
        "retrieved_at": "2026-10-04T00:00:00Z",
    }
    assert utc_now_iso().endswith("Z")


def test_clean_text_collapses_and_truncates() -> None:
    assert clean_text("  a \n b  ") == "a b"
    assert clean_text(None) == ""
    assert clean_text("one two three four", max_len=9) == "one two..."


def test_merge_nodes_dedups_by_id_and_keeps_first_values() -> None:
    first = Node(
        id="HGNC:4177",
        type=NodeType.GENE,
        label="GBA1",
        synonyms=("GBA",),
        attributes={"description": "from monarch"},
    )
    second = Node(
        id="HGNC:4177",
        type=NodeType.GENE,
        label="GBA1",
        synonyms=("GBA", "GLUC", "GBA1"),
        xrefs=("OMIM:606463",),
        attributes={"description": "other", "clinvar_total": "814"},
    )
    other = Node(id="HGNC:1665", type=NodeType.GENE, label="SCARB2")
    merged = merge_nodes([first, other, second])
    assert [node.id for node in merged] == ["HGNC:1665", "HGNC:4177"]
    gba1 = merged[1]
    assert gba1.synonyms == ("GBA", "GLUC")
    assert gba1.xrefs == ("OMIM:606463",)
    assert gba1.attributes["description"] == "from monarch"
    assert gba1.attributes["clinvar_total"] == "814"


def _edge(source: str, target: str, record: str) -> Edge:
    return Edge(
        source_id=source,
        target_id=target,
        relation=Relation.CAUSED_BY,
        provenance=Provenance(
            source="test",
            source_record_id=record,
            url="https://example.org",  # type: ignore[arg-type]
            retrieved_at=datetime(2026, 10, 4, tzinfo=UTC),
        ),
        confidence=0.9,
        evidence_type=EvidenceType.CURATED,
    )


def test_dedupe_edges_by_id_and_sorts() -> None:
    a = _edge("MONDO:2", "HGNC:1", "r1")
    b = _edge("MONDO:1", "HGNC:1", "r1")
    result = dedupe_edges([a, b, a])
    assert [edge.source_id for edge in result] == ["MONDO:1", "MONDO:2"]
