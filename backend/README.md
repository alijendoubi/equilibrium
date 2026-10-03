# Equilibrium Atlas - backend

FastAPI + Python 3.12 service for the rare-disease knowledge graph. Managed with [uv](https://docs.astral.sh/uv/).

## Layout

```
src/atlas/
  api/        FastAPI app (atlas.api.main:app) and routes
  graph/      graph construction and analytics (networkx)
  ingest/     source connectors (OMIM, HPO, MONDO, ClinVar, PubMed, ClinicalTrials.gov, NIH RePORTER, Orphanet)
  extract/    OpenAI-backed extraction, reconciliation, explanation
  models/     immutable Pydantic v2 evidence model (Node, Edge, Provenance)
  config.py   settings from environment variables
tests/        pytest suite (coverage gate: 80%)
```

## Commands (run from `backend/`)

```bash
uv sync --frozen                 # install runtime + dev deps from uv.lock
uv run uvicorn atlas.api.main:app --reload --port 8000
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run pip-audit                 # dependency vulnerability scan
docker build -t equilibrium-backend .
```

Endpoints: `GET /health`, `GET /api/v1/meta`, OpenAPI docs at `/docs`.

## Environment variables

Copy `.env.example` to `.env`. All are optional; the app and tests run without any secrets.

| Variable         | Default                  | Purpose                                  |
|------------------|--------------------------|------------------------------------------|
| `OPENAI_API_KEY` | unset                    | OpenAI access for extraction/explanation |
| `OPENAI_MODEL`   | `gpt-4.1-mini`           | Model id for OpenAI calls                |
| `NCBI_API_KEY`   | unset                    | Higher E-utilities rate limits (PubMed, ClinVar) |
| `OMIM_API_KEY`   | unset                    | OMIM API access                          |
| `CORS_ORIGINS`   | `http://localhost:3000`  | Comma-separated allowed browser origins  |
| `LOG_LEVEL`      | `INFO`                   | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` |
| `PORT`           | `8000`                   | Container listen port (Render sets this) |
