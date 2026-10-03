# ADR 0001: Stack and monorepo layout

- **Status:** Accepted
- **Date:** 2026-10-03
- **Deciders:** Team Equilibrium

## Context

We have 24 hours to deliver four things:
- a deployed prototype that judges can search live
- a repository whose README covers architecture and dataset reproduction
- graph analytics
- OpenAI-powered Extract, Reconcile and Explain

The work divides into a data and graph pipeline, which is Python-heavy (ontologies, networkx, biomedical tooling), and an interactive graph UI. Several people work in parallel, so CI, review and deploy must work from the first hour.

## Decision

- **One monorepo** with `backend/` and `frontend/`, plus `docs/`, `data/` and `scripts/`, and a single Makefile entry point (`make setup`, `make check`, `make data`).
- **Backend:**
  - Python 3.12, managed with **uv**
  - **FastAPI** (`atlas.api.main:app`, port 8000)
  - packages `api`, `graph`, `ingest`, `extract` and `models`
  - Pydantic models for the evidence contract
- **Graph:** an in-memory **networkx** graph, loaded from a dated JSON or Parquet snapshot. No graph database for the hackathon.
- **Frontend:** **Next.js 15** with TypeScript and Tailwind, managed with **pnpm** (port 3000). Unit tests use vitest and end-to-end tests use Playwright.
- **LLM:** OpenAI API with structured outputs. The model is configurable through `OPENAI_MODEL` (default `gpt-4.1-mini`).
- **Delivery:**
  - GitHub Actions for CI, security and deploys
  - Docker images on GHCR
  - frontend on Vercel, backend on Render (Docker)
  - `docker compose up --build` for local parity

## Consequences

**Positive**
- A single PR can change the API and the UI together, which keeps the contract in sync.
- The Python ecosystem gives direct access to ontology parsing, networkx community detection and the OpenAI SDK.
- No database server keeps the setup to one command, and snapshots are versioned files that diff and reproduce cleanly.
- Vercel previews per PR make UI review fast.

**Negative**
- An in-memory graph limits scale to what fits in one process. This is fine for one cluster, but not for "all the world's medical information".
- Two toolchains (uv and pnpm) to install. This is mitigated by `make setup` and Docker.
- Free-tier Render instances cold-start. Before judging, warm the instance or use a paid instance.

## Alternatives considered

| Alternative | Why not now |
|---|---|
| Neo4j or another graph DB | Extra service, more ops and slower setup. It remains an option once the graph outgrows memory, because the snapshot format maps cleanly to a bulk import. |
| Separate repos for backend and frontend | Doubles CI and review overhead, and contract drift becomes likely within 24 hours |
| Full-stack TypeScript (Next.js API routes only) | Weaker graph analytics and ontology tooling |
| Streamlit or Gradio UI | Faster to start, but cannot deliver the product craft the brief asks for: progressive reveal and an edge explanation panel |
| poetry or pip-tools | uv is faster and handles the Python version and lockfile in one tool |
