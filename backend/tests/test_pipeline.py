"""Snapshot pipeline: determinism, validation, CLI and story checks."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from atlas.ingest.common import CACHE_DIR
from atlas.models.evidence import Edge, EvidenceType, Node, NodeType, Provenance, Relation
from atlas.pipeline import __main__ as cli
from atlas.pipeline import build as build_module
from atlas.pipeline.build import (
    MANIFEST_FILE,
    SNAPSHOT_DIR,
    SNAPSHOT_FILE,
    SnapshotValidationError,
    build,
    validate,
    write,
)
from atlas.pipeline.checks import story_checks


def _edge(source: str, target: str, supporting: tuple[str, ...] = ()) -> Edge:
    return Edge(
        source_id=source,
        target_id=target,
        relation=Relation.CAUSED_BY,
        provenance=Provenance(
            source="test",
            source_record_id="r",
            url="https://example.org",  # type: ignore[arg-type]
            retrieved_at=datetime(2026, 10, 4, tzinfo=UTC),
            supporting_edge_ids=supporting,
        ),
        confidence=0.5,
        evidence_type=EvidenceType.CURATED,
    )


def test_same_cache_gives_byte_identical_snapshot() -> None:
    first, second = build(), build()
    assert first.snapshot_bytes == second.snapshot_bytes
    assert first.manifest_bytes == second.manifest_bytes
    assert first.snapshot_id == second.snapshot_id


def test_committed_snapshot_matches_committed_cache() -> None:
    """Fails when someone edits data/cache or data/curated without rebuilding."""
    output = build(CACHE_DIR)
    assert (SNAPSHOT_DIR / SNAPSHOT_FILE).read_bytes() == output.snapshot_bytes
    assert (SNAPSHOT_DIR / MANIFEST_FILE).read_bytes() == output.manifest_bytes


def test_snapshot_shape_and_manifest_counts() -> None:
    output = build()
    snapshot = json.loads(output.snapshot_bytes)
    manifest = output.manifest
    assert manifest["counts"]["nodes"] == len(snapshot["nodes"])
    assert manifest["counts"]["edges"] == len(snapshot["edges"])
    assert [n["id"] for n in snapshot["nodes"]] == sorted(n["id"] for n in snapshot["nodes"])
    assert manifest["openai_usage"]["calls"] == 0
    assert {s["source"] for s in manifest["sources"]} == {
        "monarch",
        "hpo",
        "go",
        "clinvar",
        "clinicaltrials",
        "curated",
        "reporter",
    }
    assert len(output.snapshot_bytes) < 5 * 1024 * 1024
    node_ids = {n["id"] for n in snapshot["nodes"]}
    assert all(e["source_id"] in node_ids and e["target_id"] in node_ids for e in snapshot["edges"])


def test_story_checks_pass_on_build() -> None:
    checks = story_checks(json.loads(build().snapshot_bytes))
    assert checks["hero_ok"], checks["hero_path"]
    assert checks["gap_ok"], checks["gap"]
    assert any(key.endswith("org:cure-parkinsons") for key in checks["hero_path"])


def test_story_checks_fail_when_gap_has_a_study() -> None:
    snapshot: dict[str, Any] = json.loads(build().snapshot_bytes)
    snapshot["edges"].append(
        {
            "id": "E:x",
            "source_id": "clinicaltrials:NCT0",
            "target_id": "MONDO:0012517",
            "relation": "studies_condition",
        }
    )
    assert not story_checks(snapshot)["ok"]


def test_validate_catches_dangling_edges_and_type_clashes() -> None:
    gene = Node(id="HGNC:1", type=NodeType.GENE, label="G")
    disease = Node(id="MONDO:1", type=NodeType.DISEASE, label="D")
    validate([gene, disease], [_edge("MONDO:1", "HGNC:1")])
    with pytest.raises(SnapshotValidationError, match="dangling endpoint MONDO:2") as excinfo:
        validate([gene, disease], [_edge("MONDO:2", "HGNC:1")])
    assert excinfo.value.problems
    clash = Node(id="HGNC:1", type=NodeType.DISEASE, label="G")
    with pytest.raises(SnapshotValidationError, match="conflicting types"):
        validate([gene, disease], [], all_nodes=[clash])
    with pytest.raises(SnapshotValidationError, match="missing edge"):
        validate([gene, disease], [_edge("MONDO:1", "HGNC:1", ("E:0123456789abcdef",))])
    with pytest.raises(SnapshotValidationError, match="duplicate"):
        validate([gene, gene, disease], [])


def test_validation_error_message_is_truncated() -> None:
    error = SnapshotValidationError([f"p{i}" for i in range(12)])
    assert "(+2 more)" in str(error)


def test_cli_build_offline_and_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["build", "--offline", "--out", str(tmp_path)]) == 0
    assert (tmp_path / SNAPSHOT_FILE).read_bytes() == build().snapshot_bytes
    assert cli.main(["report", "--dir", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["story_checks"]["ok"] is True


def test_cli_online_refreshes_first(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli, "refresh", lambda: calls.append("refresh"))
    assert cli.main(["build", "--out", str(tmp_path)]) == 0
    assert calls == ["refresh"]


def test_write_creates_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "snap"
    snapshot_path, manifest_path = write(build(), target)
    assert snapshot_path.is_file() and manifest_path.is_file()
    assert build_module.SCHEMA_VERSION in manifest_path.read_text(encoding="utf-8")
