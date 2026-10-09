"""Explain: prompt facts, strict schema, validator, cache, offline/template, route, CLI.

No network: OpenAI is replaced by a fake client with a ``responses.create`` method.
"""

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openai import OpenAIError

from atlas.api import explain_routes
from atlas.api.main import create_app
from atlas.config import Settings, get_settings
from atlas.explain import cli
from atlas.explain.cache import ExplanationCache, explanation_key
from atlas.explain.golden import golden_edges, nodes_for
from atlas.explain.models import ExplainRequest
from atlas.explain.prompt import PROMPT_VERSION, build_context, response_schema
from atlas.explain.service import explain_client, explain_edges
from atlas.explain.templates import RELATION_PHRASES, edge_sentence, template_explanation
from atlas.explain.validate import ExplanationRejectedError, validate_output
from atlas.graph.store import GraphStore
from atlas.models.evidence import Edge, EvidenceType, Node, NodeType, Provenance, Relation

MODEL = "gpt-test"
SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "snapshot" / "atlas-snapshot.json"


@pytest.fixture(scope="module")
def store() -> GraphStore:
    return GraphStore.from_snapshot(SNAPSHOT)


@pytest.fixture(scope="module")
def golden(store: GraphStore) -> tuple[Edge, ...]:
    return golden_edges(store)


def _node(node_id: str, label: str, node_type: NodeType) -> Node:
    return Node(id=node_id, type=node_type, label=label)


NODES = {
    n.id: n
    for n in (
        _node("MONDO:1", "Disease One", NodeType.DISEASE),
        _node("HGNC:1", "GENE1", NodeType.GENE),
        _node("clinicaltrials:NCT1", "Trial One", NodeType.STUDY),
        _node("org:one", "Org One", NodeType.FUNDER),
    )
}


def _edge(
    source: str,
    relation: Relation,
    target: str,
    *,
    evidence: EvidenceType = EvidenceType.CURATED,
    confidence: float = 0.9,
    contradicted_by: tuple[str, ...] = (),
) -> Edge:
    return Edge(
        source_id=source,
        target_id=target,
        relation=relation,
        provenance=Provenance(
            source="monarch",
            source_record_id=f"rec-{source}-{target}",
            url="https://example.org/rec",
            retrieved_at="2026-10-03T23:21:41Z",
            evidence_quote="GENE1 variants were found in 12 patients",
        ),
        confidence=confidence,
        evidence_type=evidence,
        contradicted_by=contradicted_by,
    )


CAUSE = _edge("MONDO:1", Relation.CAUSED_BY, "HGNC:1")
STUDY = _edge("clinicaltrials:NCT1", Relation.STUDIES_CONDITION, "MONDO:1", confidence=0.6)
EDGES = (CAUSE, STUDY)


class FakeResponses:
    def __init__(self, outputs: Sequence[str | Exception]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        usage = SimpleNamespace(input_tokens=100, output_tokens=20)
        return SimpleNamespace(output_text=item, usage=usage)


class FakeClient:
    def __init__(self, *outputs: str | Exception) -> None:
        self.responses = FakeResponses(outputs)


def _output(steps: list[dict[str, Any]], summary: str = "A short summary.") -> str:
    return json.dumps({"steps": steps, "summary": summary, "caveats": ["Needs expert review."]})


GOOD = _output(
    [
        {
            "text": "Disease One comes from GENE1 changes.",
            "edge_ids": [CAUSE.id],
            "is_hypothesis": False,
        },
        {"text": "Trial One studies Disease One.", "edge_ids": [STUDY.id], "is_hypothesis": False},
    ]
)


def _run(client: Any, tmp_path: Path, audience: Any = "family") -> Any:
    cache = ExplanationCache.load(tmp_path / "explanations.json")
    return explain_edges(EDGES, NODES, audience=audience, client=client, model=MODEL, cache=cache)


# ---- prompt and schema -------------------------------------------------------------------


def test_prompt_contains_only_edge_facts() -> None:
    context = build_context(EDGES, NODES)
    assert CAUSE.id in context and STUDY.id in context
    assert "Disease One (disease, MONDO:1) --caused_by--> GENE1 (gene, HGNC:1)" in context
    assert "quote: GENE1 variants were found in 12 patients" in context
    assert "https://example.org/rec" in context
    assert "2026-10-03" not in context  # retrieval timestamps are not facts
    assert "Org One" not in context  # nodes outside the edges never leak in


def test_schema_restricts_edge_ids_to_request() -> None:
    schema = response_schema([CAUSE.id, STUDY.id])
    assert schema["format"]["strict"] is True
    step = schema["format"]["schema"]["properties"]["steps"]["items"]
    assert step["properties"]["edge_ids"]["items"]["enum"] == [CAUSE.id, STUDY.id]
    assert step["additionalProperties"] is False


# ---- validator ---------------------------------------------------------------------------


def test_validator_accepts_cited_output() -> None:
    draft = validate_output(GOOD, EDGES, build_context(EDGES, NODES))
    assert [s.edge_ids for s in draft.steps] == [(CAUSE.id,), (STUDY.id,)]


@pytest.mark.parametrize(
    "bad",
    [
        _output([{"text": "Uncited.", "edge_ids": [], "is_hypothesis": False}]),
        _output([{"text": "Unknown.", "edge_ids": ["E:ffffffffffffffff"], "is_hypothesis": False}]),
        _output([]),
        _output([{"text": "", "edge_ids": [CAUSE.id], "is_hypothesis": False}]),
        _output([{"text": "Dose is 25 mg/kg.", "edge_ids": [CAUSE.id], "is_hypothesis": False}]),
        _output([{"text": "Fine.", "edge_ids": [CAUSE.id], "is_hypothesis": False}], summary=""),
        "not json",
    ],
)
def test_validator_rejects_bad_output(bad: str) -> None:
    with pytest.raises(ExplanationRejectedError):
        validate_output(bad, EDGES, build_context(EDGES, NODES))


def test_validator_allows_numbers_from_edges() -> None:
    text = _output(
        [{"text": "12 patients had it.", "edge_ids": [CAUSE.id], "is_hypothesis": False}]
    )
    assert validate_output(text, EDGES, build_context(EDGES, NODES)).steps


def test_validator_requires_contradicted_edge_to_be_cited() -> None:
    contradicted = _edge("HGNC:1", Relation.RISK_FACTOR_FOR, "MONDO:1", contradicted_by=("E:x",))
    edges = (CAUSE, contradicted)
    text = _output([{"text": "Cause.", "edge_ids": [CAUSE.id], "is_hypothesis": False}])
    with pytest.raises(ExplanationRejectedError, match="contradicted"):
        validate_output(text, edges, build_context(edges, NODES))


# ---- service: live, retry, fallback, cache, offline --------------------------------------


def test_live_call_validates_and_caches(tmp_path: Path) -> None:
    client = FakeClient(GOOD)
    outcome = _run(client, tmp_path)
    assert outcome.response.source == "live"
    assert outcome.response.ai_generated is True
    assert outcome.response.model == MODEL
    assert outcome.usage.as_dict() == {
        MODEL: {"calls": 1, "input_tokens": 100, "output_tokens": 20}
    }
    call = client.responses.calls[0]
    assert call["model"] == MODEL
    assert call["text"]["format"]["strict"] is True
    assert len(outcome.cache) == 1

    outcome.cache.save()
    second_client = FakeClient()
    again = _run(second_client, tmp_path)
    assert again.response.source == "cache"
    assert again.response.ai_generated is True
    assert again.response.steps == outcome.response.steps
    assert second_client.responses.calls == []


def test_rejected_output_retries_once_then_succeeds(tmp_path: Path) -> None:
    uncited = _output([{"text": "Uncited.", "edge_ids": [], "is_hypothesis": False}])
    client = FakeClient(uncited, GOOD)
    outcome = _run(client, tmp_path)
    assert outcome.response.source == "live"
    assert len(client.responses.calls) == 2


def test_two_failures_fall_back_to_template(tmp_path: Path) -> None:
    unknown = _output([{"text": "X.", "edge_ids": ["E:ffffffffffffffff"], "is_hypothesis": False}])
    client = FakeClient(unknown, OpenAIError("boom"))
    outcome = _run(client, tmp_path)
    assert outcome.response.source == "template"
    assert outcome.response.ai_generated is False
    assert len(outcome.cache) == 0
    assert len(client.responses.calls) == 2


def test_offline_uses_template_without_calling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_OFFLINE", "1")
    client = FakeClient(GOOD)
    outcome = _run(client, tmp_path)
    assert outcome.response.source == "template"
    assert client.responses.calls == []


def test_offline_still_serves_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run(FakeClient(GOOD), tmp_path).cache.save()
    monkeypatch.setenv("ATLAS_OFFLINE", "1")
    assert _run(None, tmp_path).response.source == "cache"


def test_cache_key_is_deterministic_and_content_sensitive() -> None:
    key = explanation_key(MODEL, "family", EDGES, NODES)
    assert key == explanation_key(MODEL, "family", tuple(reversed(EDGES)), NODES)
    assert key != explanation_key(MODEL, "researcher", EDGES, NODES)
    assert key != explanation_key("other-model", "family", EDGES, NODES)
    changed = _edge("clinicaltrials:NCT1", Relation.STUDIES_CONDITION, "MONDO:1", confidence=0.5)
    assert key != explanation_key(MODEL, "family", (CAUSE, changed), NODES)


def test_malformed_cache_entry_is_ignored(tmp_path: Path) -> None:
    key = explanation_key(MODEL, "family", EDGES, NODES)
    cache = ExplanationCache(tmp_path / "c.json", {key: {"steps": "nope"}})
    outcome = explain_edges(EDGES, NODES, audience="family", client=None, model=MODEL, cache=cache)
    assert outcome.response.source == "template"


def test_explain_client_is_none_without_key_or_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    assert explain_client(Settings()) is None
    monkeypatch.setenv("ATLAS_OFFLINE", "1")
    assert explain_client(Settings(OPENAI_API_KEY="sk-test")) is None
    monkeypatch.delenv("ATLAS_OFFLINE")
    assert explain_client(Settings(OPENAI_API_KEY="sk-test")) is not None


# ---- templates ---------------------------------------------------------------------------


def test_every_relation_has_a_phrase() -> None:
    assert set(RELATION_PHRASES) == set(Relation)


@pytest.mark.parametrize(
    ("source", "relation", "target", "expected"),
    [
        ("MONDO:1", Relation.CAUSED_BY, "HGNC:1", "Disease One is caused by changes in GENE1."),
        (
            "HGNC:1",
            Relation.RISK_FACTOR_FOR,
            "MONDO:1",
            "Changes in GENE1 are a risk factor for Disease One.",
        ),
        (
            "clinicaltrials:NCT1",
            Relation.STUDIES_CONDITION,
            "MONDO:1",
            "The study Trial One focuses on Disease One.",
        ),
        ("org:one", Relation.FUNDS, "clinicaltrials:NCT1", "Org One funds Trial One."),
        (
            "org:one",
            Relation.REPRESENTS,
            "MONDO:1",
            "Org One represents people affected by Disease One.",
        ),
        ("HGNC:1", Relation.PARTICIPATES_IN, "MONDO:1", "GENE1 takes part in Disease One."),
        ("MONDO:1", Relation.HAS_PHENOTYPE, "HGNC:1", "Disease One can show the feature GENE1."),
    ],
)
def test_template_direction(source: str, relation: Relation, target: str, expected: str) -> None:
    assert edge_sentence(_edge(source, relation, target), NODES) == expected


def test_template_marks_inferred_and_low_confidence() -> None:
    inferred = _edge("HGNC:1", Relation.RISK_FACTOR_FOR, "MONDO:1", evidence=EvidenceType.INFERRED)
    result = template_explanation((inferred, STUDY), NODES, "researcher")
    assert result.steps[0].is_hypothesis is True
    assert result.steps[0].text.startswith("Hypothesis")
    assert "confidence 0.90" in result.steps[0].text
    assert any("inferred" in c for c in result.caveats)
    assert any(STUDY.id in c for c in result.caveats)
    assert result.source == "template" and result.model is None
    assert result.prompt_version == PROMPT_VERSION


def test_request_dedupes_and_limits_ids() -> None:
    assert ExplainRequest(edge_ids=[" E:a ", "E:a", "E:b"]).edge_ids == ["E:a", "E:b"]
    with pytest.raises(ValueError):
        ExplainRequest(edge_ids=["   "])


# ---- golden path, route and CLI against the committed snapshot ---------------------------


def test_golden_path_found(golden: tuple[Edge, ...]) -> None:
    pairs = [(e.source_id, e.relation, e.target_id) for e in golden]
    assert ("MONDO:0009267", Relation.CAUSED_BY, "HGNC:4177") in pairs
    assert ("HGNC:4177", Relation.RISK_FACTOR_FOR, "MONDO:0008199") in pairs
    assert ("org:cure-parkinsons", Relation.FUNDS, "clinicaltrials:NCT05778617") in pairs


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(Settings())
    app.state.explain_cache_path = tmp_path / "explanations.json"
    with TestClient(app) as test_client:
        app.state.explain_cache_path = tmp_path / "explanations.json"
        yield test_client


def test_route_template_for_golden_path(api: TestClient, golden: tuple[Edge, ...]) -> None:
    ids = [e.id for e in golden]
    response = api.post("/api/v1/explain", json={"edge_ids": ids})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "template" and body["ai_generated"] is False
    assert [s["edge_ids"] for s in body["steps"]] == [[i] for i in ids]
    assert "Gaucher disease type II is caused by changes in GBA1." in body["steps"][0]["text"]


def test_route_live_with_fake_client(
    api: TestClient, golden: tuple[Edge, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    edge = golden[0]
    output = _output(
        [{"text": "Type 2 is linked to GBA1.", "edge_ids": [edge.id], "is_hypothesis": False}]
    )
    fake = FakeClient(output)
    monkeypatch.setattr(explain_routes, "explain_client", lambda _settings: fake)
    api.app.dependency_overrides[get_settings] = lambda: Settings(EXPLAIN_LIVE=True)  # type: ignore[attr-defined]
    body = api.post(
        "/api/v1/explain", json={"edge_ids": [edge.id], "audience": "researcher"}
    ).json()
    assert body["source"] == "live"
    assert body["model"] == get_settings().openai_model_explain
    again = api.post("/api/v1/explain", json={"edge_ids": [edge.id], "audience": "researcher"})
    assert again.json()["source"] == "cache"


def test_route_unknown_edge_404(api: TestClient, golden: tuple[Edge, ...]) -> None:
    response = api.post("/api/v1/explain", json={"edge_ids": [golden[0].id, "E:0000000000000000"]})
    assert response.status_code == 404
    assert "E:0000000000000000" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    "payload",
    [
        {"edge_ids": []},
        {"edge_ids": [f"E:{i:016x}" for i in range(13)]},
        {"edge_ids": ["E:0000000000000000"], "audience": "doctor"},
        {},
    ],
)
def test_route_validation_422(api: TestClient, payload: dict[str, Any]) -> None:
    assert api.post("/api/v1/explain", json=payload).status_code == 422


def test_cli_golden_without_key_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = tmp_path / "explanations.json"
    code = cli.main(["--snapshot", str(SNAPSHOT), "--cache", str(cache), "golden"])
    assert code == 0
    assert not cache.exists()
    assert "nothing written" in capsys.readouterr().out


def test_cli_precompute_with_fake_client(
    tmp_path: Path,
    golden: tuple[Edge, ...],
    store: GraphStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edge = golden[1]
    output = _output(
        [{"text": "Type 3 is linked to GBA1.", "edge_ids": [edge.id], "is_hypothesis": False}]
    )
    fake = FakeClient(output, output)
    monkeypatch.setattr(cli, "explain_client", lambda _settings: fake)
    paths = tmp_path / "paths.json"
    paths.write_text(json.dumps([[edge.id]]), encoding="utf-8")
    cache = tmp_path / "explanations.json"
    args = ["--snapshot", str(SNAPSHOT), "--cache", str(cache), "precompute", "--paths", str(paths)]
    assert cli.main(args) == 0
    saved = json.loads(cache.read_text(encoding="utf-8"))["explanations"]
    assert {entry["audience"] for entry in saved.values()} == {"family", "researcher"}
    assert nodes_for(store, [edge])  # endpoints resolve


def test_cli_precompute_unknown_id(tmp_path: Path) -> None:
    paths = tmp_path / "paths.json"
    paths.write_text(json.dumps([["E:0000000000000000"]]), encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.main(["--snapshot", str(SNAPSHOT), "precompute", "--paths", str(paths)])


def test_route_never_calls_openai_unless_explain_live(
    api: TestClient, golden: tuple[Edge, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeClient(_output([]))
    monkeypatch.setattr(explain_routes, "explain_client", lambda _settings: fake)

    body = api.post("/api/v1/explain", json={"edge_ids": [golden[0].id]}).json()

    assert body["source"] == "template"
    assert fake.responses.calls == []


def test_route_rate_limits_per_client(api: TestClient, golden: tuple[Edge, ...]) -> None:
    api.app.dependency_overrides[get_settings] = lambda: Settings(EXPLAIN_RATE_PER_MINUTE=2)  # type: ignore[attr-defined]
    payload = {"edge_ids": [golden[0].id]}
    headers = {"x-forwarded-for": "203.0.113.7"}

    codes = [
        api.post("/api/v1/explain", json=payload, headers=headers).status_code for _ in range(3)
    ]
    other = api.post("/api/v1/explain", json=payload, headers={"x-forwarded-for": "198.51.100.1"})

    assert codes == [200, 200, 429]
    assert other.status_code == 200


def test_cache_dir_follows_snapshot_path(tmp_path: Path) -> None:
    settings = Settings(SNAPSHOT_PATH=tmp_path / "data" / "snapshot" / "s.json")

    assert settings.cache_dir == tmp_path / "data" / "cache"
    assert Settings().explain_live is False


def test_live_call_caps_output_tokens(golden: tuple[Edge, ...], store: GraphStore) -> None:
    edge = golden[0]
    fake = FakeClient(
        _output(
            [{"text": "Type 2 is linked to GBA1.", "edge_ids": [edge.id], "is_hypothesis": False}]
        )
    )

    explain_edges(
        (edge,),
        nodes_for(store, (edge,)),
        audience="family",
        client=fake,
        model="gpt-6.1-sol",
        cache=ExplanationCache(Path("unused.json")),
    )

    assert fake.responses.calls[0]["max_output_tokens"] == 1500


def test_path_ends_follow_the_chain_not_edge_direction(store: GraphStore) -> None:
    from atlas.explain.templates import path_ends

    gd2_gene = next(
        e
        for e in store.edges_for("MONDO:0009266", relations=[Relation.CAUSED_BY])
        if e.target_id == "HGNC:4177"
    )
    funds = next(e for e in store.edges_for("org:cure-parkinsons", relations=[Relation.FUNDS]))
    study = next(
        e
        for e in store.edges_for(
            "clinicaltrials:NCT05778617", relations=[Relation.STUDIES_CONDITION]
        )
        if e.target_id == "MONDO:0008199"
    )
    risk = next(
        e
        for e in store.edges_for("HGNC:4177", relations=[Relation.RISK_FACTOR_FOR])
        if e.target_id == "MONDO:0008199"
    )
    chain = (gd2_gene, risk, study, funds)

    assert path_ends(chain) == ("MONDO:0009266", "org:cure-parkinsons")
    summary = template_explanation(chain, nodes_for(store, chain)).summary
    assert summary.startswith("This path links Gaucher disease type II to Cure Parkinson")
    assert path_ends(()) is None
    assert path_ends((risk,)) == ("HGNC:4177", "MONDO:0008199")


@pytest.mark.parametrize(
    ("source", "record", "expected"),
    [
        ("monarch", "infores:omim|HGNC:4177|biolink:causes|MONDO:0009266", "OMIM via Monarch"),
        ("monarch", "infores:orphanet|x", "Orphanet via Monarch"),
        ("monarch", "infores:other|x", "Monarch Initiative"),
        ("go", "HGNC:4177", "Gene Ontology annotation"),
        ("clinicaltrials", "NCT05778617", "ClinicalTrials.gov NCT05778617"),
        ("pubmed", "PMID:1", "PubMed PMID:1"),
        ("curated", "x", "team-curated, cited source"),
        ("other", "r", "other r"),
    ],
)
def test_source_citation_is_readable(source: str, record: str, expected: str) -> None:
    from datetime import UTC, datetime

    from atlas.explain.templates import source_citation

    prov = Provenance(
        source=source, source_record_id=record, retrieved_at=datetime(2026, 10, 4, tzinfo=UTC)
    )
    assert source_citation(prov) == expected
