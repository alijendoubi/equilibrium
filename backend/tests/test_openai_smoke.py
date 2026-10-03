"""Logic of scripts/openai_smoke.py with a mocked client (no network)."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from atlas.config import Settings
from atlas.extract.openai_client import OpenAIKeyMissingError

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "openai_smoke.py"
SECRET = "sk-test-secret-123"  # noqa: S105 - fake key for redaction tests


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("openai_smoke", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["openai_smoke"] = module
    spec.loader.exec_module(module)
    return module


smoke = _load_script()


def make_client(output_text: str = '{"status": "ok"}', dims: int = 3) -> MagicMock:
    client = MagicMock()
    client.responses.create.return_value = SimpleNamespace(output_text=output_text)
    client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1] * dims)]
    )
    client.files.create.return_value = SimpleNamespace(id="file-1")
    client.batches.create.return_value = SimpleNamespace(id="batch-1", status="validating")
    return client


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    return Settings()


def test_chat_models_are_deduplicated_by_model(settings: Settings) -> None:
    assert smoke.chat_models(settings) == {
        "gpt-6.1-sol": ["extract", "explain"],
        "gpt-6-luna": ["reconcile"],
    }


def test_run_checks_calls_each_chat_model_and_one_embedding(settings: Settings) -> None:
    client = make_client()

    results = smoke.run_checks(client, settings, batch=False)

    assert [(r.name, r.model, r.ok) for r in results] == [
        ("responses (extract,explain)", "gpt-6.1-sol", True),
        ("responses (reconcile)", "gpt-6-luna", True),
        ("embeddings", "text-embedding-3-small", True),
    ]
    first_call = client.responses.create.call_args_list[0].kwargs
    assert first_call["model"] == "gpt-6.1-sol"
    assert first_call["text"]["format"]["type"] == "json_schema"
    assert first_call["text"]["format"]["strict"] is True
    client.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small", input=smoke.EMBED_INPUT
    )
    client.files.create.assert_not_called()
    client.batches.create.assert_not_called()


def test_batch_flag_uploads_jsonl_and_creates_batch(settings: Settings) -> None:
    client = make_client()

    results = smoke.run_checks(client, settings, batch=True)

    assert results[-1].name == "batch submit"
    assert results[-1].ok is True
    assert "batch-1" in results[-1].detail
    upload = client.files.create.call_args.kwargs
    assert upload["purpose"] == "batch"
    lines = upload["file"][1].decode("utf-8").splitlines()
    assert len(lines) == 1
    request = json.loads(lines[0])
    assert request["url"] == "/v1/responses"
    assert request["body"]["model"] == "gpt-6.1-sol"
    client.batches.create.assert_called_once_with(
        input_file_id="file-1", endpoint="/v1/responses", completion_window="24h"
    )


@pytest.mark.parametrize("output_text", ['{"status": "nope"}', "not json"])
def test_bad_structured_output_fails_the_check(settings: Settings, output_text: str) -> None:
    results = smoke.run_checks(make_client(output_text=output_text), settings, batch=False)

    assert [r.ok for r in results] == [False, False, True]


def test_empty_embedding_fails_the_check(settings: Settings) -> None:
    results = smoke.run_checks(make_client(dims=0), settings, batch=False)

    assert results[-1].ok is False
    assert "empty embedding" in results[-1].detail


def test_errors_are_reported_without_the_key(settings: Settings) -> None:
    client = make_client()
    client.responses.create.side_effect = RuntimeError(f"Incorrect API key provided: {SECRET}")
    client.embeddings.create.side_effect = RuntimeError("bad key sk-proj-abc*****xyz")

    results = smoke.run_checks(client, settings, batch=False)

    assert not any(r.ok for r in results)
    rendered = smoke.format_table(results)
    assert SECRET not in rendered
    assert "sk-proj-abc" not in rendered
    assert "RuntimeError" in rendered


def test_redact_without_secret_still_masks_key_shapes() -> None:
    assert smoke.redact("token sk-abc123 here", None) == "token sk-*** here"


def test_format_table_shows_pass_and_fail() -> None:
    table = smoke.format_table(
        [
            smoke.CheckResult("embeddings", "text-embedding-3-small", True, "1536 dims"),
            smoke.CheckResult("responses (reconcile)", "gpt-6-luna", False, "BadRequestError"),
        ]
    )

    lines = table.splitlines()
    assert lines[0].split() == ["check", "model", "result", "detail"]
    assert "PASS" in lines[2] and "1536 dims" in lines[2]
    assert "FAIL" in lines[3]


def test_main_returns_zero_when_all_pass(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    code = smoke.main([], settings=settings, client_factory=lambda _: make_client())

    out = capsys.readouterr().out
    assert code == 0
    assert "3/3 checks passed" in out
    assert SECRET not in out


def test_main_returns_one_on_failure(settings: Settings) -> None:
    def factory(_: Settings) -> Any:
        return make_client(output_text="{}")

    assert smoke.main(["--batch"], settings=settings, client_factory=factory) == 1


def test_main_returns_two_without_key(capsys: pytest.CaptureFixture[str]) -> None:
    def factory(_: Settings) -> Any:
        raise OpenAIKeyMissingError("OPENAI_API_KEY is not set.")

    assert smoke.main([], settings=Settings(), client_factory=factory) == 2
    assert "OPENAI_API_KEY is not set" in capsys.readouterr().err


def test_main_without_key_uses_real_factory(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke.main([]) == 2
    assert "OPENAI_API_KEY is not set" in capsys.readouterr().err
