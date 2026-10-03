"""OpenAI smoke test: structured outputs per chat model, one embedding, optional Batch submit.

Run from backend/:
    uv run python scripts/openai_smoke.py           # Responses + embeddings
    uv run python scripts/openai_smoke.py --batch   # also upload a 1-line JSONL and create a Batch

Needs OPENAI_API_KEY (environment or backend/.env). The key is never printed.
Exit code: 0 all checks passed, 1 at least one failed, 2 no key configured.
"""

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any

from atlas.config import Settings, get_settings
from atlas.extract.openai_client import OpenAIKeyMissingError, create_openai_client

SMOKE_PROMPT = 'Return the JSON object {"status": "ok"}.'
SMOKE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"status": {"type": "string", "enum": ["ok"]}},
    "required": ["status"],
    "additionalProperties": False,
}
TEXT_FORMAT: dict[str, Any] = {
    "format": {
        "type": "json_schema",
        "name": "smoke_check",
        "schema": SMOKE_SCHEMA,
        "strict": True,
    }
}
EMBED_INPUT = "Gaucher disease"
BATCH_ENDPOINT = "/v1/responses"
BATCH_WINDOW = "24h"
_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-*]+")


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one smoke check."""

    name: str
    model: str
    ok: bool
    detail: str


def redact(text: str, secret: str | None) -> str:
    """Remove the configured key and anything key-shaped from a message."""
    cleaned = text.replace(secret, "***") if secret else text
    return _KEY_PATTERN.sub("sk-***", cleaned)


def _run(name: str, model: str, secret: str | None, check: Callable[[], str]) -> CheckResult:
    try:
        return CheckResult(name, model, True, check())
    except Exception as exc:  # noqa: BLE001 - a smoke test reports every failure as a row
        detail = redact(f"{type(exc).__name__}: {exc}", secret)
        return CheckResult(name, model, False, detail)


def check_structured_output(client: Any, model: str) -> str:
    """Responses API with a strict JSON schema; the reply must parse to {"status": "ok"}."""
    response = client.responses.create(model=model, input=SMOKE_PROMPT, text=TEXT_FORMAT)
    parsed = json.loads(response.output_text)
    if parsed != {"status": "ok"}:
        raise ValueError(f"unexpected structured output: {parsed!r}")
    return "structured output ok"


def check_embedding(client: Any, model: str) -> str:
    """One embedding request; the vector must be non-empty."""
    response = client.embeddings.create(model=model, input=EMBED_INPUT)
    dims = len(response.data[0].embedding)
    if dims == 0:
        raise ValueError("empty embedding")
    return f"{dims} dims"


def build_batch_line(model: str) -> bytes:
    """A single Batch API request line targeting the Responses endpoint."""
    line = {
        "custom_id": "smoke-1",
        "method": "POST",
        "url": BATCH_ENDPOINT,
        "body": {"model": model, "input": SMOKE_PROMPT, "text": TEXT_FORMAT},
    }
    return (json.dumps(line) + "\n").encode("utf-8")


def check_batch(client: Any, model: str) -> str:
    """Upload a 1-line JSONL and create a Batch (does not wait for completion)."""
    uploaded = client.files.create(
        file=("openai_smoke.jsonl", build_batch_line(model)), purpose="batch"
    )
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint=BATCH_ENDPOINT,
        completion_window=BATCH_WINDOW,
    )
    return f"batch {batch.id} status={batch.status}"


def chat_models(settings: Settings) -> dict[str, list[str]]:
    """Distinct chat models mapped to the roles that use them (one call per model)."""
    roles = {
        "extract": settings.openai_model_extract,
        "explain": settings.openai_model_explain,
        "reconcile": settings.openai_model_reconcile,
    }
    grouped: dict[str, list[str]] = {}
    for role, model in roles.items():
        grouped.setdefault(model, []).append(role)
    return grouped


def run_checks(client: Any, settings: Settings, *, batch: bool) -> list[CheckResult]:
    """Run every smoke check and collect results; never raises."""
    key = settings.openai_api_key
    secret = key.get_secret_value() if key is not None else None
    results = [
        _run(
            f"responses ({','.join(roles)})",
            model,
            secret,
            partial(check_structured_output, client, model),
        )
        for model, roles in chat_models(settings).items()
    ]
    embed_model = settings.openai_embed_model
    results.append(
        _run("embeddings", embed_model, secret, partial(check_embedding, client, embed_model))
    )
    if batch:
        batch_model = settings.openai_model_extract
        results.append(
            _run("batch submit", batch_model, secret, partial(check_batch, client, batch_model))
        )
    return results


def format_table(results: Sequence[CheckResult]) -> str:
    """Plain-text pass/fail table."""
    headers = ("check", "model", "result", "detail")
    rows = [(r.name, r.model, "PASS" if r.ok else "FAIL", r.detail) for r in results]
    widths = [max(len(str(row[i])) for row in (headers, *rows)) for i in range(3)]

    def render(row: Sequence[str]) -> str:
        cells = [str(cell).ljust(widths[i]) for i, cell in enumerate(row[:3])]
        return "  ".join([*cells, row[3]])

    divider = "  ".join("-" * w for w in widths) + "  ------"
    return "\n".join([render(headers), divider, *(render(row) for row in rows)])


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    client_factory: Callable[[Settings], Any] = create_openai_client,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--batch", action="store_true", help="also upload a 1-line JSONL and create a Batch"
    )
    args = parser.parse_args(argv)
    resolved = settings if settings is not None else get_settings()
    try:
        client = client_factory(resolved)
    except OpenAIKeyMissingError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    results = run_checks(client, resolved, batch=args.batch)
    print(format_table(results))
    passed = sum(r.ok for r in results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
