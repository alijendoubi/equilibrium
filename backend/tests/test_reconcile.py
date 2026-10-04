"""Reconcile: resolver, merge, embeddings cache, OpenAI choice, search, CLI. No network."""

import json
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from atlas.models.evidence import Node, NodeType
from atlas.reconcile import cli
from atlas.reconcile.embeddings import EmbeddingCache, cosine, embedding_key
from atlas.reconcile.llm_choice import (
    Candidate,
    Choice,
    DecisionCache,
    choose,
    decision_key,
    parse_choice,
)
from atlas.reconcile.resolver import merge_duplicates, resolve
from atlas.reconcile.search import SearchIndex
from atlas.reconcile.usage import ModelUsage, UsageRecord, usage_from_response

EMBED_MODEL = "text-embedding-3-small"


def disease(node_id: str, label: str, *synonyms: str, xrefs: Sequence[str] = ()) -> Node:
    return Node(
        id=node_id, type=NodeType.DISEASE, label=label, synonyms=synonyms, xrefs=tuple(xrefs)
    )


GD2 = disease(
    "MONDO:0009266",
    "Gaucher disease type II",
    "acute neuronopathic Gaucher disease",
    xrefs=("OMIM:230900", "ORPHA:77260"),
)
GD3 = disease(
    "MONDO:0009267",
    "Gaucher disease type III",
    "chronic neuronopathic Gaucher disease",
    xrefs=("OMIM:231000",),
)
PD = disease("MONDO:1040030", "GBA1-related Parkinson disease", "GBA-associated Parkinson's")
GBA1 = Node(id="HGNC:4177", type=NodeType.GENE, label="GBA1", synonyms=("GBA", "GCase gene"))
NODES = (GD2, GD3, PD, GBA1)


class FakeEmbeddings:
    def __init__(self, table: dict[str, list[float]]):
        self.table = table
        self.calls = 0

    def create(self, model: str, input: list[str]) -> Any:
        self.calls += 1
        data = [SimpleNamespace(embedding=self.table.get(t, [0.0, 0.0, 1.0])) for t in input]
        return SimpleNamespace(data=data, usage=SimpleNamespace(prompt_tokens=len(input)))


class FakeResponses:
    def __init__(self, answer: str):
        self.answer = answer
        self.calls = 0
        self.last: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.calls += 1
        self.last = kwargs
        usage = SimpleNamespace(input_tokens=10, output_tokens=5)
        return SimpleNamespace(output_text=self.answer, usage=usage)


def fake_client(answer: str = '{"node_id":"none","rationale":"x"}', table: Any = None) -> Any:
    return SimpleNamespace(responses=FakeResponses(answer), embeddings=FakeEmbeddings(table or {}))


@pytest.fixture(autouse=True)
def online(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_OFFLINE", raising=False)


# --- deterministic resolution -------------------------------------------------------------


@pytest.mark.parametrize(
    ("mention", "expected", "method"),
    [
        ("Gaucher disease type II", "MONDO:0009266", "exact"),
        ("gaucher disease, type 2", "MONDO:0009266", "exact"),
        ("OMIM:231000", "MONDO:0009267", "xref"),
        ("HGNC:4177", "HGNC:4177", "xref"),
        ("chronic neuronopathic Gaucher", "MONDO:0009267", "synonym"),
        ("GBA", "HGNC:4177", "synonym"),
    ],
)
def test_deterministic_methods(mention: str, expected: str, method: str) -> None:
    (resolution,) = resolve([mention], NODES).resolutions

    assert (resolution.node_id, resolution.method) == (expected, method)


def test_unmatched_mention_without_embeddings_or_llm_is_none() -> None:
    (resolution,) = resolve(["zzqx unrelated"], NODES).resolutions

    assert resolution.node_id is None
    assert resolution.method == "none"


def test_partial_lexical_match_goes_to_llm_and_is_cached(tmp_path: Path) -> None:
    client = fake_client('{"node_id":"MONDO:0009266","rationale":"type 2 is acute"}')
    cache = DecisionCache(tmp_path / "d.json")

    first = resolve(["Gaucher acute type"], NODES, decisions=cache, client=client)
    (resolution,) = first.resolutions

    assert resolution.method == "llm"
    assert resolution.node_id == "MONDO:0009266"
    assert first.usage.total_calls == 1
    assert first.decisions is not None
    second = resolve(["Gaucher acute type"], NODES, decisions=first.decisions, client=client)
    assert second.usage.total_calls == 0
    assert client.responses.calls == 1


def test_llm_answer_outside_candidates_becomes_none(tmp_path: Path) -> None:
    client = fake_client('{"node_id":"MONDO:9999999","rationale":"made up"}')

    result = resolve(
        ["Gaucher acute type"], NODES, decisions=DecisionCache(tmp_path / "d"), client=client
    )

    assert result.resolutions[0].node_id is None


def test_offline_never_calls_openai(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_OFFLINE", "1")
    client = fake_client('{"node_id":"MONDO:0009266","rationale":"x"}')

    result = resolve(
        ["Gaucher acute type"], NODES, decisions=DecisionCache(tmp_path / "d"), client=client
    )

    assert result.resolutions[0].node_id is None
    assert client.responses.calls == 0


def test_several_synonym_matches_are_ambiguous(tmp_path: Path) -> None:
    twin = disease("ORPHA:999", "Other", "GBA")
    client = fake_client('{"node_id":"HGNC:4177","rationale":"gene symbol"}')

    (resolution,) = resolve(
        ["GBA"], (*NODES, twin), decisions=DecisionCache(tmp_path / "d"), client=client
    ).resolutions

    assert resolution.method == "llm"
    assert {c for c, _ in resolution.candidates} == {"HGNC:4177", "ORPHA:999"}


def test_ambiguous_without_decision_cache_is_none() -> None:
    (resolution,) = resolve(["Gaucher acute type"], NODES).resolutions

    assert resolution.node_id is None
    assert resolution.rationale is not None


# --- embeddings ---------------------------------------------------------------------------


def _cache_with(tmp_path: Path, table: dict[str, list[float]]) -> EmbeddingCache:
    cache, usage = EmbeddingCache(EMBED_MODEL, tmp_path / "e.json").with_fetched(
        list(table), fake_client(table=table)
    )
    assert usage.total_calls == 1
    return cache


def test_embedding_match_accepts_clear_winner(tmp_path: Path) -> None:
    table = {
        "infant lysosomal neuro disease": [1.0, 0.0, 0.0],
        "Gaucher disease type II": [0.99, 0.05, 0.0],
        "Gaucher disease type III": [0.2, 0.9, 0.0],
    }
    cache = _cache_with(tmp_path, table)

    (resolution,) = resolve(["infant lysosomal neuro disease"], NODES, embeddings=cache).resolutions

    assert (resolution.node_id, resolution.method) == ("MONDO:0009266", "embedding")


def test_embedding_close_call_asks_llm(tmp_path: Path) -> None:
    table = {
        "neuro gaucher": [1.0, 1.0, 0.0],
        "Gaucher disease type II": [1.0, 0.95, 0.0],
        "Gaucher disease type III": [0.95, 1.0, 0.0],
    }
    cache = _cache_with(tmp_path, table)
    client = fake_client('{"node_id":"MONDO:0009267","rationale":"chronic"}')

    (resolution,) = resolve(
        ["neuro gaucher"],
        NODES,
        embeddings=cache,
        decisions=DecisionCache(tmp_path / "d"),
        client=client,
    ).resolutions

    assert (resolution.node_id, resolution.method) == ("MONDO:0009267", "llm")


def test_embedding_far_match_is_none(tmp_path: Path) -> None:
    table = {"weather": [0.0, 0.0, 1.0], "Gaucher disease type II": [1.0, 0.0, 0.0]}
    cache = _cache_with(tmp_path, table)

    (resolution,) = resolve(["weather"], NODES, embeddings=cache).resolutions

    assert resolution.node_id is None


def test_embedding_cache_roundtrip_and_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = _cache_with(tmp_path, {"GBA1": [0.1, 0.2, 0.3]})
    cache.save()

    loaded = EmbeddingCache.load(EMBED_MODEL, tmp_path)
    assert loaded.path.name == f"{EMBED_MODEL}.json"
    assert EmbeddingCache.load(EMBED_MODEL, tmp_path / "empty").get("GBA1") is None
    raw = json.loads((tmp_path / "e.json").read_text(encoding="utf-8"))
    assert embedding_key(EMBED_MODEL, "gba1") in raw["vectors"]
    assert cache.missing(["GBA1", "gba1", "", "new", "NEW"]) == ("new",)

    monkeypatch.setenv("ATLAS_OFFLINE", "1")
    client = fake_client(table={"new": [1.0, 0.0, 0.0]})
    same, usage = cache.with_fetched(["new"], client)
    assert same is cache
    assert usage.total_calls == 0
    assert cache.with_fetched(["GBA1"], None)[0] is cache


def test_cosine_edge_cases() -> None:
    assert cosine([], []) == 0.0
    assert cosine([1.0], [1.0, 0.0]) == 0.0
    assert cosine([0.0, 0.0], [0.0, 0.0]) == 0.0
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


# --- OpenAI choice ------------------------------------------------------------------------


def test_choice_schema_enumerates_only_candidates(tmp_path: Path) -> None:
    client = fake_client('{"node_id":"A:1","rationale":"r"}')
    candidates = [Candidate("A:1", "a", "disease"), Candidate("B:2", "b", "disease", ("bee",))]

    choice, cache, usage = choose(
        "x", candidates, client=client, model="gpt-6-luna", cache=DecisionCache(tmp_path / "d")
    )

    enum = client.responses.last["text"]["format"]["schema"]["properties"]["node_id"]["enum"]
    assert enum == ["A:1", "B:2", "none"]
    assert client.responses.last["model"] == "gpt-6-luna"
    assert choice.node_id == "A:1"
    assert len(cache) == 1
    assert usage.as_dict()["gpt-6-luna"] == {"calls": 1, "input_tokens": 10, "output_tokens": 5}


@pytest.mark.parametrize("text", ["not json", '{"rationale":"no id"}', '{"node_id":"none"}'])
def test_parse_choice_rejects_bad_output(text: str) -> None:
    assert parse_choice(text, ["A:1"], "m").node_id is None


def test_decision_cache_persists(tmp_path: Path) -> None:
    path = tmp_path / "reconcile" / "decisions.json"
    key = decision_key("m", "x", ["B:2", "A:1"])
    assert key == decision_key("m", "x", ["A:1", "B:2"])

    DecisionCache(path).with_choice(key, Choice("A:1", "because", "m")).save()

    assert DecisionCache.load(path).get(key) == Choice("A:1", "because", "m")
    assert len(DecisionCache.load(tmp_path / "missing.json")) == 0


# --- usage --------------------------------------------------------------------------------


def test_usage_merge_and_defensive_parsing() -> None:
    a = UsageRecord.single("m", ModelUsage(1, 2, 3))
    b = UsageRecord.single("m", ModelUsage(1, 1, 1)).merge(UsageRecord.single("n", ModelUsage(1)))

    merged = a.merge(b)

    assert merged.as_dict()["m"] == {"calls": 2, "input_tokens": 3, "output_tokens": 4}
    assert merged.total_calls == 3
    assert usage_from_response(object()) == ModelUsage(calls=1)


# --- merge duplicates ---------------------------------------------------------------------


def test_merge_prefers_mondo_and_unions_names() -> None:
    orpha = disease("ORPHA:77260", "Gaucher disease type 2", "GD2", xrefs=("OMIM:230900",))
    omim = Node(
        id="OMIM:230900",
        type=NodeType.DISEASE,
        label="GAUCHER DISEASE, TYPE II",
        attributes={"source": "omim"},  # type: ignore[arg-type]
    )

    canonical, aliases = merge_duplicates([orpha, omim, GD2, GBA1])

    assert [n.id for n in canonical] == ["HGNC:4177", "MONDO:0009266"]
    merged = next(n for n in canonical if n.id == "MONDO:0009266")
    assert "GD2" in merged.synonyms
    assert {"ORPHA:77260", "OMIM:230900"} <= set(merged.xrefs)
    assert merged.attributes["source"] == "omim"
    assert aliases == {"ORPHA:77260": "MONDO:0009266", "OMIM:230900": "MONDO:0009266"}
    assert orpha.id == "ORPHA:77260"


def test_merge_keeps_different_types_apart() -> None:
    canonical, aliases = merge_duplicates([GBA1, disease("MONDO:0000001", "GBA1")])

    assert len(canonical) == 2
    assert aliases == {}


# --- search -------------------------------------------------------------------------------


def test_search_reasons_and_ranking() -> None:
    index = SearchIndex.build(NODES)

    exact = index.search("GBA1")[0]
    synonym = index.search("acute neuronopathic Gaucher")[0]
    by_id = index.search("OMIM:230900")[0]
    prefix = index.search("Gauch")

    assert (exact.node_id, exact.match_reason, exact.score) == ("HGNC:4177", "exact", 1.0)
    assert (synonym.node_id, synonym.match_reason) == ("MONDO:0009266", "synonym")
    assert by_id.node_id == "MONDO:0009266"
    assert {h.node_id for h in prefix} >= {"MONDO:0009266", "MONDO:0009267"}
    assert index.search("") == ()
    assert index.search("GBA1", types=["phenotype"]) == ()
    assert [h.node_id for h in index.search("GBA1", types=["disease"])] == ["MONDO:1040030"]
    assert len(index.search("Gaucher", limit=1)) == 1
    assert "atlas nodes" in index.searched[0]


def test_search_semantic_uses_embeddings(tmp_path: Path) -> None:
    table = {"lysosome problem": [1.0, 0.0, 0.0], "GCase gene": [0.95, 0.1, 0.0]}
    index = SearchIndex.build(NODES, _cache_with(tmp_path, table))

    (hit,) = index.search("lysosome problem")

    assert (hit.node_id, hit.match_reason, hit.matched_text) == (
        "HGNC:4177",
        "semantic",
        "GCase gene",
    )
    assert "semantic" in index.searched[0]


# --- CLI ----------------------------------------------------------------------------------


def _snapshot(tmp_path: Path) -> Path:
    path = tmp_path / "snap.json"
    path.write_text(
        json.dumps({"nodes": [n.model_dump(mode="json") for n in NODES]}), encoding="utf-8"
    )
    return path


def test_cli_resolve_and_embed_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_client_or_none", lambda: None)
    snap = _snapshot(tmp_path)
    root = tmp_path / "cache"

    assert cli.main(["--cache-root", str(root), "resolve", "--nodes", str(snap), "GBA"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["node_id"] == "HGNC:4177"

    assert cli.main(["--cache-root", str(root), "embed", "--nodes", str(snap)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["still_missing"] > 0
    assert summary["openai_usage"] == {}


def test_cli_embed_with_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = fake_client(table={})
    monkeypatch.setattr(cli, "_client_or_none", lambda: client)

    result = cli.cmd_embed(NODES, tmp_path)

    assert result["still_missing"] == 0
    assert (tmp_path / "embeddings" / f"{EMBED_MODEL}.json").exists()


def test_cli_missing_snapshot(tmp_path: Path) -> None:
    assert cli.main(["resolve", "--nodes", str(tmp_path / "none.json"), "x"]) == cli.EXIT_USAGE


def test_cli_accepts_bare_list(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text(json.dumps([GBA1.model_dump(mode="json")]), encoding="utf-8")

    assert cli.load_nodes(path) == (GBA1,)


def test_client_or_none_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from atlas.config import get_settings

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(Path(__file__).parent)
    get_settings.cache_clear()

    assert cli._client_or_none() is None
