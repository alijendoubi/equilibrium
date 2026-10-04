"""Online refresh orchestration (with every network call faked)."""

from pathlib import Path
from typing import Any

import pytest

from atlas.ingest import __main__ as cli
from atlas.ingest import refresh
from atlas.ingest.common import PoliteClient, read_cache, write_cache
from tests._ingest_helpers import load_fixture


def test_refresh_writes_each_source_in_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    order: list[str] = []

    def fake_fetch(name: str, client: PoliteClient, cache_dir: Path) -> dict[str, Any]:
        order.append(name)
        return {"meta": {"source": name}}

    monkeypatch.setattr(refresh, "fetch_source", fake_fetch)
    refresh.refresh(("clinvar", "monarch"), cache_dir=tmp_path)
    assert order == ["monarch", "clinvar"]
    assert read_cache("clinvar", "payload", tmp_path) == {"meta": {"source": "clinvar"}}


def test_fetch_source_dispatches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, Any]] = []
    monkeypatch.setattr(refresh.monarch, "fetch", lambda c: calls.append(("monarch", None)) or {})
    monkeypatch.setattr(refresh.hpo, "fetch", lambda c, ids: calls.append(("hpo", ids)) or {})
    monkeypatch.setattr(refresh.go, "fetch", lambda c, wl: calls.append(("go", len(wl))) or {})
    monkeypatch.setattr(refresh.clinvar, "fetch", lambda c, k: calls.append(("clinvar", k)) or {})
    monkeypatch.setattr(refresh.clinicaltrials, "fetch", lambda c: calls.append(("ct", None)) or {})
    write_cache(load_fixture("monarch"), "monarch", "payload", tmp_path)
    monkeypatch.setenv("NCBI_API_KEY", "secret")
    refresh.get_settings.cache_clear()
    client = PoliteClient()
    for name in refresh.SOURCES:
        refresh.fetch_source(name, client, tmp_path)
    client.close()
    names = [name for name, _ in calls]
    assert names == ["monarch", "hpo", "go", "clinvar", "ct"]
    assert calls[1][1] and calls[1][1][0].startswith("HP:")
    assert calls[3][1] == "secret"
    assert refresh._interval("clinvar") < refresh._interval("clinicaltrials")
    assert refresh._interval("monarch") == refresh.DEFAULT_INTERVAL_S
    with pytest.raises(ValueError, match="unknown source"):
        refresh.fetch_source("nope", client, tmp_path)


def test_cli_passes_selected_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, ...]] = []
    monkeypatch.setattr(cli, "refresh", lambda sources: seen.append(tuple(sources)))
    assert cli.main(["fetch", "--source", "clinvar"]) == 0
    assert cli.main(["fetch"]) == 0
    assert seen == [("clinvar",), refresh.SOURCES]
