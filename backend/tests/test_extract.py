"""OpenAI Extract (#18): PubMed parsing, strict schema, validation, edges, cache, pipeline, eval.

No network: PubMed is a recorded efetch XML fixture behind httpx.MockTransport and OpenAI is a
fake client that returns canned structured output.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from atlas.extract import cli
from atlas.extract import pubmed as pm
from atlas.extract.claims import (
    ALLOWED_RELATIONS,
    ClaimsCache,
    candidate_hash,
    candidate_nodes,
    extract_abstract,
    parse_output,
    schema,
    validate_claims,
)
from atlas.extract.edges import extract_stage, to_graph
from atlas.extract.eval import evaluate, load_gold
from atlas.ingest.common import PoliteClient
from atlas.models.evidence import EvidenceType, Node, NodeType, Relation
from atlas.pipeline import build as build_module
from atlas.pipeline.build import build

FIXTURE = Path(__file__).parent / "fixtures" / "extract" / "efetch_sample.xml"
MODEL = "gpt-test"
PSAP = "HGNC:9498"
PSAPD = "MONDO:0012719"
GAUCHER = "MONDO:0018150"
GOOD_QUOTE = "sphingolipidosis due to mutations in the prosaposin gene"


def _abstracts() -> tuple[pm.Abstract, ...]:
    return pm.parse_efetch_xml(FIXTURE.read_text(encoding="utf-8"))


def _saposins() -> pm.Abstract:
    return next(a for a in _abstracts() if a.pmid == "1402395")


def _nodes() -> tuple[Node, ...]:
    return (
        Node(id=PSAP, type=NodeType.GENE, label="PSAP"),
        Node(id=PSAPD, type=NodeType.DISEASE, label="combined PSAP deficiency"),
        Node(id=GAUCHER, type=NodeType.DISEASE, label="Gaucher disease"),
        Node(id="HP:0001250", type=NodeType.PHENOTYPE, label="Seizure"),
    )


def _claim(**overrides: str) -> dict[str, str]:
    claim = {
        "subject_id": PSAPD,
        "relation": "caused_by",
        "object_id": PSAP,
        "quote": GOOD_QUOTE,
        "polarity": "supports",
        "certainty": "high",
    }
    return {**claim, **overrides}


class FakeOpenAI:
    """Records calls; answers every request with the same canned claims."""

    def __init__(self, claims: list[dict[str, str]]):
        self.calls: list[dict[str, Any]] = []
        self.responses = SimpleNamespace(create=self._create)
        self._claims = claims

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text=json.dumps({"claims": self._claims}),
            usage=SimpleNamespace(input_tokens=1000, output_tokens=50),
        )


@pytest.fixture
def abstracts_path(tmp_path: Path) -> Path:
    payload = {
        "meta": {
            "url": pm.ESEARCH_URL,
            "source_version": None,
            "retrieved_at": "2026-10-04T07:00:00Z",
        },
        "queries": {"q": ["1402395", "9497856"]},
        "abstracts": [a.as_json() for a in _abstracts()],
    }
    return pm.write_abstracts(payload, tmp_path / "pubmed" / "abstracts.json")


# --- PubMed ---------------------------------------------------------------------------------


def test_parse_efetch_xml_fields() -> None:
    records = {a.pmid: a for a in _abstracts()}
    assert set(records) == {"9497856", "1402395"}
    saposins = records["1402395"]
    assert saposins.title.startswith("Saposins: structure")
    assert saposins.year == "1992"
    assert saposins.journal == "J Lipid Res"
    assert saposins.authors == ("Kishimoto Y", "Hiraiwa M", "O'Brien JS")
    assert GOOD_QUOTE in saposins.abstract
    assert saposins.node_id == "PMID:1402395"
    assert saposins.url == "https://pubmed.ncbi.nlm.nih.gov/1402395/"
    assert pm.Abstract.from_json(saposins.as_json()) == saposins


def test_parse_skips_records_without_abstract_and_reads_labels() -> None:
    xml = (
        "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>"
        "<Journal><Title>J</Title><JournalIssue><PubDate><MedlineDate>2001 Jan-Feb</MedlineDate>"
        "</PubDate></JournalIssue></Journal><ArticleTitle>T</ArticleTitle><Abstract>"
        '<AbstractText Label="BACKGROUND">a <i>b</i></AbstractText><AbstractText>c</AbstractText>'
        "</Abstract><AuthorList><Author><CollectiveName>Group</CollectiveName></Author>"
        "</AuthorList></Article></MedlineCitation></PubmedArticle>"
        "<PubmedArticle><MedlineCitation><PMID>2</PMID><Article><ArticleTitle>x</ArticleTitle>"
        "</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
    )
    (record,) = pm.parse_efetch_xml(xml)
    assert record.abstract == "BACKGROUND: a b c"
    assert (record.year, record.journal, record.authors) == ("2001", "J", ("Group",))


def test_select_pmids_round_robin_dedupes_and_caps() -> None:
    assert pm.select_pmids([["1", "2", "3"], ["2", "4"]], cap=3) == ["1", "2", "4"]
    assert pm.select_pmids([], cap=3) == []


def test_fetch_corpus_with_mock_transport(tmp_path: Path) -> None:
    xml = FIXTURE.read_text(encoding="utf-8")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "esearch" in request.url.path:
            return httpx.Response(200, json={"esearchresult": {"idlist": ["9497856", "1402395"]}})
        return httpx.Response(200, text=xml)

    client = PoliteClient(min_interval_s=0, transport=httpx.MockTransport(handler))
    payload = pm.fetch_corpus(client, queries=("a", "b"), cap=5, api_key="k")
    assert [a["pmid"] for a in payload["abstracts"]] == ["1402395", "9497856"]
    assert all(r.url.params["api_key"] == "k" for r in seen)
    assert "hasabstract" in seen[0].url.params["term"]
    path = pm.write_abstracts(payload, tmp_path / "a.json")
    assert len(pm.load_abstracts(path)) == 2
    assert pm.load_abstracts(tmp_path / "missing.json") == ()


def test_committed_corpus_is_bounded() -> None:
    assert pm.DEFAULT_ABSTRACTS_PATH.stat().st_size < 1_500_000
    abstracts = pm.load_abstracts()
    assert 0 < len(abstracts) <= pm.MAX_PMIDS
    assert len({a.pmid for a in abstracts}) == len(abstracts)


# --- schema and validation ------------------------------------------------------------------


def test_schema_restricts_ids_and_relations_to_enums() -> None:
    ids = [n.id for n in candidate_nodes(_nodes())]
    assert "HP:0001250" not in ids  # phenotypes are not candidates
    fmt = schema(ids)["format"]
    assert fmt["strict"] is True
    item = fmt["schema"]["properties"]["claims"]["items"]
    assert item["properties"]["subject_id"]["enum"] == ids
    assert item["properties"]["object_id"]["enum"] == ids
    assert set(item["properties"]["relation"]["enum"]) == {r.value for r in ALLOWED_RELATIONS}
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])


def test_validation_drops_fabricated_quotes_unknown_ids_and_bad_values() -> None:
    abstract = _saposins().abstract
    ids = [PSAP, PSAPD, GAUCHER]
    raw = [
        _claim(quote="  sphingolipidosis due to\n mutations in the   prosaposin gene "),
        _claim(),  # duplicate triple
        _claim(quote="prosaposin causes Parkinson disease"),  # fabricated
        _claim(subject_id="MONDO:9999999"),  # unknown id
        _claim(relation="treats"),  # not whitelisted
        _claim(object_id=PSAPD),  # self loop
        _claim(certainty="certain"),
        {"subject_id": PSAPD},  # malformed
    ]
    kept, dropped = validate_claims(raw, abstract, ids)
    assert len(kept) == 1 and dropped == 7
    assert kept[0].quote == GOOD_QUOTE


def test_parse_output_tolerates_garbage() -> None:
    assert parse_output("not json") == []
    assert parse_output("[1]") == []
    assert parse_output('{"claims": [{"a": 1}]}') == [{"a": 1}]


# --- extraction, cache, offline -------------------------------------------------------------


def test_extract_calls_once_then_serves_cache(tmp_path: Path) -> None:
    candidates = candidate_nodes(_nodes())
    client = FakeOpenAI([_claim(), _claim(quote="invented")])
    cache = ClaimsCache.load(tmp_path / "claims.json")
    first, cache, usage = extract_abstract(
        _saposins(), candidates, client=client, model=MODEL, cache=cache
    )
    assert first is not None and len(first.claims) == 1 and first.dropped == 1
    assert usage.as_dict() == {MODEL: {"calls": 1, "input_tokens": 1000, "output_tokens": 50}}
    assert client.calls[0]["text"]["format"]["strict"] is True
    assert PSAP in client.calls[0]["input"]
    cache.save()

    reloaded = ClaimsCache.load(tmp_path / "claims.json")
    second, _, usage2 = extract_abstract(
        _saposins(), candidates, client=client, model=MODEL, cache=reloaded
    )
    assert second == first
    assert len(client.calls) == 1 and usage2.total_calls == 0
    text = (tmp_path / "claims.json").read_text(encoding="utf-8")
    reloaded.save()
    assert (tmp_path / "claims.json").read_text(encoding="utf-8") == text


def test_offline_or_no_client_never_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = candidate_nodes(_nodes())
    cache = ClaimsCache.load(tmp_path / "c.json")
    result, _, usage = extract_abstract(
        _saposins(), candidates, client=None, model=MODEL, cache=cache
    )
    assert result is None and usage.total_calls == 0
    monkeypatch.setenv("ATLAS_OFFLINE", "1")
    client = FakeOpenAI([_claim()])
    result, _, _ = extract_abstract(
        _saposins(), candidates, client=client, model=MODEL, cache=cache
    )
    assert result is None and client.calls == []


def test_candidate_hash_changes_with_candidates() -> None:
    nodes = candidate_nodes(_nodes())
    assert candidate_hash(nodes) != candidate_hash(nodes[:-1])


# --- edges ----------------------------------------------------------------------------------


def _extraction(tmp_path: Path, claims: list[dict[str, str]]) -> Any:
    client = FakeOpenAI(claims)
    cache = ClaimsCache.load(tmp_path / "x.json")
    extraction, _, _ = extract_abstract(
        _saposins(), candidate_nodes(_nodes()), client=client, model=MODEL, cache=cache
    )
    return extraction


def test_edges_are_inferred_with_openai_extractor_and_pmid_provenance(tmp_path: Path) -> None:
    extraction = _extraction(tmp_path, [_claim(polarity="contradicts", certainty="medium")])
    nodes, edges = to_graph(
        [extraction], {"1402395": _saposins()}, datetime(2026, 10, 4, tzinfo=UTC)
    )
    (pub,) = nodes
    assert pub.id == "PMID:1402395" and pub.type is NodeType.PUBLICATION
    assert pub.attributes["year"] == "1992" and pub.attributes["journal"] == "J Lipid Res"
    claim_edge = next(e for e in edges if e.relation is Relation.CAUSED_BY)
    assert claim_edge.evidence_type is EvidenceType.INFERRED
    assert claim_edge.provenance.extractor == f"openai:{MODEL}"
    assert claim_edge.provenance.source == "pubmed"
    assert claim_edge.provenance.source_record_id == "PMID:1402395"
    assert str(claim_edge.provenance.url) == "https://pubmed.ncbi.nlm.nih.gov/1402395/"
    assert claim_edge.provenance.evidence_quote == GOOD_QUOTE
    assert claim_edge.confidence == 0.45 and claim_edge.confidence_reasons
    assert claim_edge.qualifiers["polarity"] == "contradicts"
    assert claim_edge.contradicted_by == ()
    mentions = sorted(e.target_id for e in edges if e.relation is Relation.MENTIONS)
    assert mentions == sorted([PSAP, PSAPD])
    assert all(e.confidence < 0.7 for e in edges)


def test_to_graph_skips_empty_and_unknown(tmp_path: Path) -> None:
    extraction = _extraction(tmp_path, [_claim(quote="nope")])
    assert to_graph([extraction], {"1402395": _saposins()}, datetime.now(UTC)) == ((), ())
    assert to_graph([extraction], {}, datetime.now(UTC)) == ((), ())


# --- pipeline -------------------------------------------------------------------------------


def test_pipeline_with_empty_claims_cache_is_unchanged() -> None:
    assert build().snapshot_bytes == build(with_extract=False).snapshot_bytes
    assert build().manifest_bytes == build(with_extract=False).manifest_bytes


def test_extract_stage_none_without_claims(tmp_path: Path, abstracts_path: Path) -> None:
    assert extract_stage(_nodes(), MODEL, tmp_path / "none.json", abstracts_path) is None
    ClaimsCache(tmp_path / "other.json").save()
    other = _extraction(tmp_path, [_claim()])
    ClaimsCache(tmp_path / "other.json", {"stale-key": other}).save()
    assert extract_stage(_nodes(), MODEL, tmp_path / "other.json", abstracts_path) is None


def test_pipeline_adds_cached_claims_deterministically(
    tmp_path: Path, abstracts_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph_nodes = cli.graph_nodes()
    claims_path = tmp_path / "extract" / "claims.json"
    code = cli.run(graph_nodes, abstracts_path, claims_path, FakeOpenAI([_claim()]), MODEL)
    assert code == 0
    monkeypatch.setattr(
        build_module,
        "_run_extract",
        lambda nodes, cache, flag: (
            None if flag is False else extract_stage(nodes, MODEL, claims_path, abstracts_path)
        ),
    )
    first, second = build(), build()
    assert first.snapshot_bytes == second.snapshot_bytes
    snapshot = json.loads(first.snapshot_bytes)
    assert any(n["id"] == "PMID:1402395" for n in snapshot["nodes"])
    usage = first.manifest["openai_usage"]
    assert usage["calls"] == 2 and usage["input_tokens"] == 2000
    assert usage["models"][MODEL]["output_tokens"] == 100
    assert "pubmed" in [s["source"] for s in first.manifest["sources"]]
    assert build(with_extract=False).snapshot_bytes != first.snapshot_bytes


# --- CLI and eval ---------------------------------------------------------------------------


def test_cli_run_without_key_writes_nothing(
    tmp_path: Path, abstracts_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.run(_nodes(), abstracts_path, tmp_path / "c.json", None, MODEL) == 0
    assert not (tmp_path / "c.json").exists()
    assert "No OPENAI_API_KEY" in capsys.readouterr().out


def test_cli_report_and_eval(
    tmp_path: Path, abstracts_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claims_path = tmp_path / "claims.json"
    cli.run(_nodes(), abstracts_path, claims_path, FakeOpenAI([_claim()]), MODEL, limit=5)
    capsys.readouterr()
    assert (
        cli.main(["--claims", str(claims_path), "--abstracts", str(abstracts_path), "report"]) == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["claims"] == 1 and report["abstracts_cached"] == 2
    assert report["by_relation"] == {"caused_by": 1}

    gold = tmp_path / "gold.jsonl"
    gold.write_text("", encoding="utf-8")
    assert cli.main(["--claims", str(claims_path), "eval", "--gold", str(gold)]) == 0
    assert "no gold claims" in capsys.readouterr().out
    rows = [
        {"pmid": "1402395", "subject_id": PSAPD, "relation": "caused_by", "object_id": PSAP},
        {
            "pmid": "PMID:1402395",
            "subject_id": PSAP,
            "relation": "risk_factor_for",
            "object_id": GAUCHER,
        },
    ]
    gold.write_text("\n".join(json.dumps(r) for r in rows) + "\n\n", encoding="utf-8")
    assert cli.main(["--claims", str(claims_path), "eval", "--gold", str(gold)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["precision"] == 1.0 and result["recall"] == 0.5


def test_eval_maths(tmp_path: Path) -> None:
    extraction = _extraction(tmp_path, [_claim()])
    gold = (
        ("PMID:1402395", PSAPD, "caused_by", PSAP),
        ("PMID:1402395", PSAP, "risk_factor_for", GAUCHER),
    )
    result = evaluate([extraction], gold)
    assert (result.matched, result.predicted, result.gold) == (1, 1, 2)
    assert result.f1 == pytest.approx(2 / 3)
    other = evaluate([extraction], (("PMID:1", PSAP, "caused_by", GAUCHER),))
    assert other.predicted == 0 and other.precision == 0.0 and other.f1 == 0.0
    assert evaluate([], ()).recall == 0.0
    assert load_gold(tmp_path / "missing.jsonl") == ()


def test_cli_fetch_uses_polite_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {"meta": {}, "queries": {}, "abstracts": [a.as_json() for a in _abstracts()]}
    monkeypatch.setattr(cli, "fetch_corpus", lambda client, api_key=None: payload)
    out = tmp_path / "abs.json"
    assert cli.main(["--abstracts", str(out), "fetch"]) == 0
    assert "2 abstracts" in capsys.readouterr().out
    assert len(pm.load_abstracts(out)) == 2
