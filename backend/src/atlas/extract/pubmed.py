"""Bounded PubMed corpus for the gba1 slice via NCBI E-utilities (esearch + efetch).

``fetch_corpus`` runs a fixed list of queries, keeps at most ``MAX_PMIDS`` unique PMIDs that
have an abstract, fetches the abstracts as XML and returns a compact JSON payload. The CLI
writes it to ``data/cache/pubmed/abstracts.json`` (committed) so Extract runs offline.
NCBI asks for <= 3 requests/s without an API key (10/s with ``NCBI_API_KEY``).
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET  # noqa: S405 - parses NCBI efetch XML only (trusted source)
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from atlas.ingest.common import CACHE_DIR, PoliteClient, clean_text, make_meta

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESEARCH_URL = f"{EUTILS}/esearch.fcgi"
EFETCH_URL = f"{EUTILS}/efetch.fcgi"
PUBMED_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
MAX_PMIDS = 150
PER_QUERY = 30
EFETCH_BATCH = 50
INTERVAL_NO_KEY_S = 0.34
INTERVAL_WITH_KEY_S = 0.11
CACHE_SOURCE = "pubmed"
CACHE_NAME = "abstracts"
DEFAULT_ABSTRACTS_PATH = CACHE_DIR / CACHE_SOURCE / f"{CACHE_NAME}.json"

# Slice queries (PROJECT_PLAN 8b). Each is restricted to records with an abstract.
QUERIES: tuple[str, ...] = (
    "(GBA[tiab] OR GBA1[tiab] OR glucocerebrosidase[tiab]) AND Parkinson*[tiab]",
    "neuronopathic[tiab] AND Gaucher[tiab]",
    "ambroxol[tiab] AND (Gaucher[tiab] OR Parkinson*[tiab])",
    '"saposin C"[tiab] AND (deficiency[tiab] OR Gaucher[tiab])',
    "(SCARB2[tiab] OR LIMP-2[tiab] OR LIMP2[tiab]) AND (glucocerebrosidase[tiab] OR GCase[tiab])",
    "(PSAP[tiab] OR prosaposin[tiab]) AND (Gaucher[tiab] OR Parkinson*[tiab] OR lysosom*[tiab])",
)
_YEAR = re.compile(r"(19|20)\d{2}")


@dataclass(frozen=True)
class Abstract:
    """One PubMed record, reduced to what Extract and the publication node need."""

    pmid: str
    title: str
    abstract: str
    year: str
    journal: str
    authors: tuple[str, ...] = ()

    @property
    def node_id(self) -> str:
        return f"PMID:{self.pmid}"

    @property
    def url(self) -> str:
        return PUBMED_URL.format(pmid=self.pmid)

    def as_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["authors"] = list(self.authors)
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Abstract:
        return cls(
            pmid=str(data["pmid"]),
            title=str(data.get("title", "")),
            abstract=str(data.get("abstract", "")),
            year=str(data.get("year", "")),
            journal=str(data.get("journal", "")),
            authors=tuple(str(a) for a in data.get("authors", ())),
        )


def _text(element: ET.Element | None) -> str:
    return clean_text("".join(element.itertext())) if element is not None else ""


def _year(article: ET.Element) -> str:
    for path in (
        ".//Article/Journal/JournalIssue/PubDate/Year",
        ".//Article/Journal/JournalIssue/PubDate/MedlineDate",
        ".//Article/ArticleDate/Year",
    ):
        match = _YEAR.search(_text(article.find(path)))
        if match:
            return match.group(0)
    return ""


def _authors(article: ET.Element) -> tuple[str, ...]:
    names = []
    for author in article.findall(".//Article/AuthorList/Author"):
        last = _text(author.find("LastName"))
        if last:
            initials = _text(author.find("Initials"))
            names.append(f"{last} {initials}".strip())
            continue
        collective = _text(author.find("CollectiveName"))
        if collective:
            names.append(collective)
    return tuple(names)


def _abstract_text(article: ET.Element) -> str:
    parts = []
    for node in article.findall(".//Article/Abstract/AbstractText"):
        text = _text(node)
        label = (node.get("Label") or "").strip()
        if text:
            parts.append(f"{label}: {text}" if label else text)
    return " ".join(parts)


def parse_efetch_xml(xml_text: str) -> tuple[Abstract, ...]:
    """Parse an efetch ``rettype=abstract, retmode=xml`` payload; skips records without text."""
    root = ET.fromstring(xml_text)  # noqa: S314 - NCBI efetch response, not user input
    records = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _text(article.find(".//MedlineCitation/PMID"))
        abstract = _abstract_text(article)
        if not pmid or not abstract:
            continue
        journal = _text(article.find(".//Article/Journal/ISOAbbreviation")) or _text(
            article.find(".//Article/Journal/Title")
        )
        records.append(
            Abstract(
                pmid=pmid,
                title=_text(article.find(".//Article/ArticleTitle")),
                abstract=abstract,
                year=_year(article),
                journal=journal,
                authors=_authors(article),
            )
        )
    return tuple(records)


def _key_params(api_key: str | None) -> dict[str, str]:
    return {"api_key": api_key} if api_key else {}


def esearch(
    client: PoliteClient, query: str, retmax: int = PER_QUERY, api_key: str | None = None
) -> list[str]:
    """PMIDs for a query (relevance order), restricted to records with an abstract."""
    params = {
        "db": "pubmed",
        "term": f"({query}) AND hasabstract",
        "retmax": str(retmax),
        "retmode": "json",
        "sort": "relevance",
        **_key_params(api_key),
    }
    data = client.get_json(ESEARCH_URL, params)
    return [str(pmid) for pmid in data.get("esearchresult", {}).get("idlist", [])]


def efetch(
    client: PoliteClient, pmids: Sequence[str], api_key: str | None = None
) -> tuple[Abstract, ...]:
    """Abstracts for the given PMIDs, fetched in batches."""
    records: list[Abstract] = []
    for start in range(0, len(pmids), EFETCH_BATCH):
        batch = pmids[start : start + EFETCH_BATCH]
        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "rettype": "abstract",
            "retmode": "xml",
            **_key_params(api_key),
        }
        records.extend(parse_efetch_xml(client.get(EFETCH_URL, params).text))
    return tuple(records)


def select_pmids(hits: Iterable[Sequence[str]], cap: int = MAX_PMIDS) -> list[str]:
    """Round-robin over the per-query hit lists so every query contributes; dedupe; cap."""
    lists = [list(h) for h in hits]
    chosen: dict[str, None] = {}
    for rank in range(max((len(h) for h in lists), default=0)):
        for hit_list in lists:
            if rank < len(hit_list) and len(chosen) < cap:
                chosen.setdefault(hit_list[rank], None)
    return list(chosen)


def fetch_corpus(
    client: PoliteClient,
    queries: Sequence[str] = QUERIES,
    cap: int = MAX_PMIDS,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Search, select and fetch the slice corpus; returns the cache payload."""
    query_hits = {query: esearch(client, query, api_key=api_key) for query in queries}
    pmids = select_pmids(query_hits.values(), cap)
    abstracts = sorted(efetch(client, pmids, api_key), key=lambda a: int(a.pmid))
    return {
        "meta": make_meta(ESEARCH_URL, None),
        "queries": query_hits,
        "abstracts": [a.as_json() for a in abstracts],
    }


def polite_client(api_key: str | None) -> PoliteClient:
    interval = INTERVAL_WITH_KEY_S if api_key else INTERVAL_NO_KEY_S
    return PoliteClient(min_interval_s=interval, retries=2, timeout_s=20.0)


def write_abstracts(payload: dict[str, Any], path: Path = DEFAULT_ABSTRACTS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, indent=1, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def load_payload(path: Path = DEFAULT_ABSTRACTS_PATH) -> dict[str, Any]:
    """The cached corpus payload, or an empty one when nothing was fetched yet."""
    if not path.is_file():
        return {"meta": {}, "queries": {}, "abstracts": []}
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def load_abstracts(path: Path = DEFAULT_ABSTRACTS_PATH) -> tuple[Abstract, ...]:
    return tuple(Abstract.from_json(item) for item in load_payload(path).get("abstracts", []))
