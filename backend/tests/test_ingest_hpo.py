"""HPO information content: ontology propagation, hpoa parsing, normalize, fetch."""

import math
from pathlib import Path

import httpx
import pytest

from atlas.ingest import hpo
from atlas.models.evidence import NodeType
from tests._ingest_helpers import assert_valid_ids, fake_client, load_fixture

OBO = """format-version: 1.2
data-version: hp/releases/2026-09-01

[Term]
id: HP:0000001
name: All

[Term]
id: HP:0000118
name: Phenotypic abnormality
is_a: HP:0000001 ! All

[Term]
id: HP:0001250
name: Seizure
alt_id: HP:0009999
is_a: HP:0000118 ! Phenotypic abnormality

[Term]
id: HP:0002123
name: Generalized myoclonic seizure
is_a: HP:0001250 ! Seizure

[Term]
id: HP:0001744
name: Splenomegaly
is_a: HP:0000118 ! Phenotypic abnormality

[Term]
id: HP:0000002
name: Old term
is_obsolete: true

[Typedef]
id: part_of
name: part of
"""

HPOA = """#description: "HPO annotations"
#version: 2026-09-02
database_id\tdisease_name\tqualifier\thpo_id\treference\tevidence\tonset\tfrequency\tsex\tmodifier\taspect\tbiocuration
OMIM:1\tA\t\tHP:0002123\tOMIM:1\tTAS\t\t\t\t\tP\tx
OMIM:2\tB\t\tHP:0009999\tOMIM:2\tTAS\t\t\t\t\tP\tx
OMIM:3\tC\t\tHP:0001744\tOMIM:3\tTAS\t\t\t\t\tP\tx
OMIM:4\tD\tNOT\tHP:0001744\tOMIM:4\tTAS\t\t\t\t\tP\tx
OMIM:4\tD\t\tHP:0000118\tOMIM:4\tTAS\t\t\t\t\tI\tx
"""


def test_parse_obo_reads_names_parents_alt_ids_and_drops_obsolete() -> None:
    names, parents, alt_ids = hpo.parse_obo(OBO.splitlines())
    assert names["HP:0002123"] == "Generalized myoclonic seizure"
    assert parents["HP:0002123"] == {"HP:0001250"}
    assert alt_ids["HP:0009999"] == "HP:0001250"
    assert "HP:0000002" not in names
    assert "part_of" not in names


def test_ic_propagates_annotations_to_ancestors() -> None:
    payload = hpo.compute_payload(
        HPOA.splitlines(),
        OBO.splitlines(),
        ["HP:0002123", "HP:0001250", "HP:0000118", "HP:0009999"],
    )
    # 3 diseases with phenotype annotations (OMIM:4 has only NOT / non-P rows).
    assert payload["annotated_diseases"] == 3
    ic = {term: float(value) for term, value in payload["ic"].items()}
    assert ic["HP:0000118"] == pytest.approx(0.0)
    assert ic["HP:0001250"] == pytest.approx(-math.log(2 / 3), abs=1e-4)  # OMIM:1 and OMIM:2
    assert ic["HP:0002123"] == pytest.approx(-math.log(1 / 3), abs=1e-4)
    assert "HP:0009999" not in ic  # alt id folded into its primary term
    assert payload["meta"]["source_version"] == "2026-09-02"
    assert payload["ontology_version"] == "hp/releases/2026-09-01"
    assert payload["labels"]["HP:0001250"] == "Seizure"


def test_unannotated_term_gets_max_ic() -> None:
    names, parents, _ = hpo.parse_obo(OBO.splitlines())
    ic, total = hpo.information_content({"D1": {"HP:0001744"}}, parents, ["HP:0002123"])
    assert total == 1
    assert ic["HP:0002123"] == pytest.approx(0.0)
    with pytest.raises(ValueError, match="no phenotype annotations"):
        hpo.information_content({}, parents, ["HP:0002123"])


def test_normalize_fixture_gives_phenotype_nodes_with_string_ic() -> None:
    result = hpo.normalize(load_fixture("hpo"))
    assert result.nodes and result.edges == ()
    assert_valid_ids(result.nodes)
    for node in result.nodes:
        assert node.type is NodeType.PHENOTYPE
        assert isinstance(node.attributes["ic"], str)
        float(node.attributes["ic"])
    assert result.notes["annotated_diseases"]


def test_fetch_downloads_once_and_computes(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        body = HPOA if request.url.path.endswith("phenotype.hpoa") else OBO
        return httpx.Response(200, text=body)

    with fake_client(handler) as client:
        payload = hpo.fetch(client, ["HP:0001250"], raw_dir=tmp_path)
        hpo.fetch(client, ["HP:0001250"], raw_dir=tmp_path)
    assert len(calls) == 2  # second call reuses the raw files
    assert (tmp_path / "hpo" / "phenotype.hpoa").is_file()
    assert set(payload["ic"]) == {"HP:0001250"}
