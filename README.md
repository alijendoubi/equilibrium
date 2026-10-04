# Equilibrium: an evidence-first atlas for rare diseases

Equilibrium is a research-grade product concept and platform for turning fragmented rare-disease knowledge into a usable, explainable, and evidence-backed atlas. It helps patient groups, clinicians, researchers, and biotech teams move from an isolated diagnosis to a credible network of related mechanisms, assets, collaborators, and action-oriented next steps.

[![CI](https://github.com/alijendoubi/equilibrium/actions/workflows/ci.yml/badge.svg)](https://github.com/alijendoubi/equilibrium/actions/workflows/ci.yml)
[![Security](https://github.com/alijendoubi/equilibrium/actions/workflows/security.yml/badge.svg)](https://github.com/alijendoubi/equilibrium/actions/workflows/security.yml)
[![Docker](https://github.com/alijendoubi/equilibrium/actions/workflows/docker.yml/badge.svg)](https://github.com/alijendoubi/equilibrium/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Team Equilibrium's submission to Hack-Nation's 7th Global AI Hackathon, Challenge 05: AI Atlas for the World's Rare Diseases, supported by OpenAI and the Buffalo Initiative.

> Status: early-stage research prototype. This README separates the product, the technology, and the current implementation status.

---

## Product thesis

Rare disease research suffers from a structural information problem: the relevant evidence is distributed across scientific literature, disease ontologies, clinical databases, patient organizations, trial registries, and funding networks. The result is a slow, fragmented, and often unproductive discovery process.

Equilibrium addresses that problem by creating an evidence-first knowledge graph that connects disease mechanisms to the entities that matter most to real-world decision-making:

- genes and variants
- disease phenotypes and related conditions
- patient communities and advocacy groups
- relevant assets such as registries, natural history studies, and models
- investigators, trial activity, and funding signals
- next-step opportunities grounded in evidence

The system is designed to help users answer three questions quickly and responsibly:

1. Who shares our disease characteristics?
2. What useful work already exists?
3. What should we do together next?

A disease is not treated as a label; it is modeled as a network of mechanisms, relationships, and opportunities.

---

## The problem we are solving

Rare diseases create one of the hardest data and discovery problems in modern medicine:

- About 10,000 rare diseases are known.
- Roughly 80% are genetic, and around 5,000 are monogenic.
- Rare diseases affect about 350 million people worldwide.
- Fewer than 5% of these diseases have an approved treatment.
- The relevant information is fragmented across many disconnected sources.
- Disease names often hide the underlying mechanism, which means naming alone is a weak proxy for similarity and therapeutic relevance.

This creates an acute challenge for patient groups, researchers, and biotech teams: they cannot easily see which communities, genes, pathways, assets, or collaborators are already connected to the disease they are studying.

The brief sets a bold objective: help rare-disease research move toward a possible treatment 10x faster.

---

## What Equilibrium does

Equilibrium is an evidence-backed atlas intended to support a patient-centered discovery journey.

### Core user journey

```text
Search "disease X"
  -> disrupted mechanism (gene, variant effect, pathway)      [cited edge]
  -> another gene / related disease with the same mechanism    [cited edge]
  -> patient group working on that disease                     [cited edge]
  -> reusable asset: registry, natural history study, model    [cited edge]
  -> next step: sourced proposal + what needs expert review
```

This is the core product idea: from an initial disease entry point, the user discovers a connected map of biological, scientific, and operational context that leads to concrete action.

### Product principles

- Evidence first: every connection in the atlas is traceable to a source.
- Transparent uncertainty: when evidence is absent, the system shows what was searched and what remains unresolved.
- Trustworthy explanation: graph paths are expressed in plain language with citations to the supporting edges.
- Actionability: the product does not stop at listing entities; it helps surface the next useful move.

### Target personas

| Persona | Need | Planned experience |
|---|---|---|
| Maria, patient org leader | Understand disease clusters, shared assets, and potential collaborators | Cluster and mechanism navigator with action view |
| Devon, newly diagnosed caregiver | Find the closest communities and appropriate context in plain language | Global search with synonym resolution and explanation |
| Priya, biotech scout | Rank and prioritize target mechanisms and related disease communities | Mechanism-first ranked cluster view |
| Dr. Osei, researcher | Identify investigators and disease groups working on the same mechanism under different gene names | Connector view and network overlap analysis |

---

## Why this is compelling

The opportunity is not simply to build another search tool. The real value lies in creating a system that can reliably connect biological meaning to patient action.

A strong evidence graph creates three strategic advantages:

1. Discovery acceleration: find hidden connections that naming-based search misses.
2. Fewer dead ends: show what work already exists before a team starts from scratch.
3. Better decision quality: make it easier to distinguish between verified relationships and uncertain ones.

This matters because research progress in rare diseases is often gated not by lack of information alone, but by lack of connectivity between information sources and decision-making workflows.

---

## Solution design

Equilibrium treats rare-disease knowledge as a graph problem, not a document retrieval problem.

Each node and edge is designed to encode meaningful evidence and provenance:

- node types: disease, gene, phenotype, variant, pathway, organization, asset, trial, investigator
- edge types: shared mechanism, phenotype overlap, co-occurrence, evidence link, collaboration, funding, asset relationship
- provenance: source, record ID, URL, retrieval date, confidence, and evidence type
- contradictions: conflicting evidence is retained and surfaced rather than hidden

This is crucial for a domain where false confidence is damaging. The system is explicitly built to be cautious, explainable, and grounded in evidence.

---

## Technical architecture

```mermaid
flowchart LR
    subgraph Sources[Public sources]
        S1[OMIM / ClinVar]
        S2[HPO / MONDO / Orphanet]
        S3[PubMed / PMC]
        S4[ClinicalTrials.gov]
        S5[NIH RePORTER]
        S6[Patient org directories]
    end

    subgraph Backend[backend/ (Python 3.12, FastAPI)]
        I[atlas.ingest<br/>fetch + cache raw records]
        X[atlas.extract<br/>OpenAI: Extract + Reconcile<br/>(structured outputs)]
        G[(atlas.graph<br/>evidence graph store<br/>networkx + JSON/Parquet snapshot)]
        A[Analytics<br/>similarity + clustering<br/>(Louvain / Leiden)]
        E[Explain layer<br/>OpenAI: path to plain language<br/>citing edge ids]
        API[atlas.api<br/>FastAPI :8000]
    end

    UI[frontend/<br/>Next.js 15 UI :3000]

    S1 & S2 & S3 & S4 & S5 & S6 --> I
    I --> X
    X --> G
    G --> A
    A --> G
    G --> API
    G --> E
    E --> API
    API --> UI
```

### Pipeline design

- Ingest: fetch and normalize source data into cached records.
- Extract: use OpenAI and structured outputs to turn source content into candidate facts and entities.
- Reconcile: normalize names and synonyms to stable biomedical identifiers.
- Graph: construct typed nodes and weighted, cited edges.
- Analytics: compute similarity, clustering, and mechanism overlap.
- Explain: transform graph paths into plain-language answers grounded in the underlying evidence.

### Why this architecture matters

This is not a monolithic AI demo. It is a production-minded system design built around:

- explicit evidence provenance
- reproducible data pipelines
- human-checkable reasoning paths
- graph analytics for similarity and clustering
- clean separation between source ingestion, extraction, and explanation

---

## Technical stack

### Backend

- Python 3.12
- FastAPI
- uv for dependency and environment management
- Pydantic v2 for type-safe models
- Graph and analytics logic built around networkx and structured data workflows

### Frontend

- Next.js 15
- TypeScript
- Tailwind CSS
- UI optimized for exploration and explanation

### Data ecosystem

- Public biomedical sources and curated domain data
- JSON/Parquet snapshots for reproducible graph artifacts
- Data conventions for raw and processed snapshots under `data/`

### AI integration

Equilibrium uses OpenAI for structured extraction, reconciliation, and explanation. The design follows a controlled pattern:

- extraction turns text into candidate facts
- reconciliation resolves biomedical ambiguity
- explanation converts graph paths into plain-language narratives
- every explanation cites the edge IDs that support it

This is essential because open-ended AI output without provenance is not acceptable in a domain where evidence quality matters.

---

## Repository layout

```text
.
├── backend/              Python 3.12 + uv + FastAPI (atlas.api.main:app)
│   └── atlas/
│       ├── api/          HTTP layer (GET /health, GET /api/v1/meta)
│       ├── graph/        evidence graph store + analytics
│       ├── ingest/       source connectors
│       ├── extract/      OpenAI extract + reconcile + explain
│       └── models/       Node / Edge / Provenance (evidence.py)
├── frontend/             Next.js 15 + TypeScript + Tailwind
├── data/                 data conventions; raw/ and processed/ are not committed
│   └── scripts/          dataset build scripts
├── docs/                 architecture, evidence model, sources, runbook, ADRs
├── scripts/github/       repo bootstrap and release scripts
├── .github/              workflows, rulesets, templates
├── docker-compose.yml
├── Makefile
├── README.md
├── .env.example
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
└── .gitignore
```

---

## Quickstart

### Prerequisites

- Python 3.12
- uv
- Node.js 20+
- pnpm
- GNU Make
- Docker (optional)

### Run locally

```bash
git clone https://github.com/alijendoubi/equilibrium.git
cd equilibrium
cp .env.example .env
make setup

make dev-backend
make dev-frontend
```

### Run with containers

```bash
docker compose up --build
```

### Common commands

```bash
make help
make check
make fmt
make clean
```

---

## Environment configuration

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Yes, for extraction / reconciliation / explanation | OpenAI access |
| `OPENAI_MODEL_EXTRACT` | No | Model used for extract |
| `OPENAI_MODEL_EXPLAIN` | No | Model used for explanation |
| `OPENAI_MODEL_RECONCILE` | No | Model used for reconciliation |
| `OPENAI_EMBED_MODEL` | No | Embedding model |
| `NCBI_API_KEY` | No | Higher PubMed / ClinVar rate limits |
| `OMIM_API_KEY` | No | OMIM access |
| `CORS_ORIGINS` | No | Allowed browser origins |
| `LOG_LEVEL` | No | Backend logging |
| `BACKEND_URL` | No | Server-side backend target |
| `NEXT_PUBLIC_API_URL` | No | Browser-side backend target |

---

The committed snapshot (`data/snapshot/atlas-snapshot.json` + `manifest.json`) is what the API serves. It is built from a compact source cache that is also committed (`data/cache/<source>/payload.json`, about 1 MB) plus the hand-curated YAML in `data/curated/`.

```bash
make data-offline   # rebuild data/snapshot/ from the committed cache: no network, no keys, ~3 s
make data-report    # counts by node type / relation + hero-path and honest-gap checks
make data           # refresh every source online (rewrites data/cache/), then rebuild (~3-5 min)
```

The same as raw commands, from `backend/`:

```bash
uv run python -m atlas.pipeline build --offline
uv run python -m atlas.pipeline report
uv run python -m atlas.pipeline build           # online
uv run python -m atlas.ingest fetch --source clinicaltrials   # refresh one source's cache
```

- **Deterministic.** The same cache gives a byte-identical snapshot and manifest (`snapshot_id` is the SHA-256 of the snapshot file; `created_at` is the latest source `retrieved_at`). A test fails if the committed snapshot is stale against the committed cache.
- **Validated.** Every node and edge passes the evidence-model pydantic models; every edge endpoint exists; supporting edge ids resolve; no id has two types. The build fails otherwise.
- **Online refresh** is polite: identifying User-Agent, timeouts, retries with backoff, rate limits (ClinicalTrials.gov ~50 req/min, NCBI 3 req/s or 10 with `NCBI_API_KEY`). HPO downloads `phenotype.hpoa` and `hp.obo` (~47 MB) into `data/raw/hpo/` (gitignored); only the IC map for slice phenotypes is committed.
- **No OpenAI step yet.** `manifest.openai_usage` is a zero placeholder until Extract/Reconcile land.

| Source (connector) | What we take | Cached |
|---|---|---|
| Monarch API v3 (`ingest/monarch.py`) | seed MONDO diseases and HGNC genes (labels, synonyms, xrefs, descriptions); OMIM- and Orphanet-sourced gene-disease links (`caused_by`, `risk_factor_for`); HPO disease-phenotype annotations (`has_phenotype`) | trimmed records |
| HPO release (`ingest/hpo.py`) | phenotype information content, IC = -ln(fraction of annotated diseases with the term or a descendant), propagated over `hp.obo` | IC map + release version |
| GO via Monarch (`ingest/go.py`) | biological-process annotations of seed genes under the whitelist in `data/curated/mechanisms.yaml` (`participates_in`) | matching annotations |
| ClinVar E-utilities (`ingest/clinvar.py`) | pathogenic / likely-pathogenic record counts per seed gene (gene attributes) | counts |
| ClinicalTrials.gov v2 (`ingest/clinicaltrials.py`) | bounded queries for Gaucher, saposin C, GBA-PD, ambroxol, venglustat, PR001 and neighbour diseases, plus the seed NCTs (`studies_condition`) | trimmed studies |
| Curated (`ingest/curated.py`) | patient groups, funders, assets (`represents`, `funds`, `studies_condition`, `mentions`); "no dedicated org found" coverage seeds | YAML in `data/curated/` |

Not ingested yet: PubMed, NIH RePORTER, Orphadata, OMIM (its licence restricts redistribution; OMIM-sourced links arrive through Monarch with attribution).

The project stores raw downloaded data separately from reproducible, built outputs. See [data/README.md](data/README.md) for the snapshot conventions and provenance manifest design.

---

## Status and roadmap

### Current status

Last updated: 2026-10-03

**Phase 1: Repo bootstrap (M1) — largely complete**

- [x] Challenge brief reviewed and documented
- [x] Monorepo scaffold created for backend and frontend
- [x] Documentation, architecture, evidence model, and planning materials added
- [x] Repository ruleset and review flow configured
- [x] Security reporting and conduct policy implemented
- [ ] CI, security, and deployment workflows green on `main`
- [ ] Vercel and Render connected with required secrets

**Phase 2: Graph slice (M2) — not started**

- [x] Disease cluster selected: GBA1 / Gaucher / lysosomal dysfunction
- [x] Curated organizations and asset notes drafted
- [ ] Ingest for MONDO, HPO, ClinVar, and PubMed in the selected slice
- [ ] OpenAI Extract and Reconcile into evidence edges
- [ ] `make data` reproduces a dated graph snapshot

**Phase 3: Trust layer (M3) — not started**

- [ ] Confidence scoring
- [ ] Contradiction tracking
- [ ] Coverage reporting
- [ ] Explain layer with edge citations and evidence transparency

**Phase 4: UI journey (M4) — not started**

- [ ] Search
- [ ] Cluster exploration
- [ ] Edge explanation panel
- [ ] Patient action view

**Phase 5: Submission (M5) — not started**

See [docs/SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md).

### Planning references

- [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)
- [docs/EXECUTION_PLAN.md](docs/EXECUTION_PLAN.md)
- [docs/RUNBOOK.md](docs/RUNBOOK.md)

---

## Development workflow

- Branches follow `feat|fix|docs|chore|data/<short-desc>` naming
- PR titles follow Conventional Commits because PRs are squash-merged and the title becomes the commit message
- `main` is protected and requires PR review by the code owner (`@alijendoubi`)
- Required checks include backend validation, frontend validation, title checks, and secrets scanning

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [docs/RUNBOOK.md](docs/RUNBOOK.md).

---

## Team

| Name | Role | GitHub |
|---|---|---|
| Ali Jendoubi | Lead, code owner | [@alijendoubi](https://github.com/alijendoubi) |
| Khaled Md Saifullah | TBD | [@sagorhossain972](https://github.com/sagorhossain972) |
| Clara Hajj | TBD | [@clara578](https://github.com/clara578) |

---

## Why this matters to the challenge

This project addresses a clear challenge statement with a product shape that is practical, evidence-driven, and immediately understandable to users:

- It recognizes the disease knowledge problem as messy and fragmented.
- It proposes a graph-based solution rooted in biomedical structure and provenance.
- It treats AI as a reasoning assistant rather than a source of final truth.
- It centers the experience around patient and investigator needs, not just technical novelty.
- It delivers a realistic roadmap from data ingest to explainable product experience.

**Phase 2: Graph slice (M2), not started**
- [x] Disease cluster chosen: GBA1/GCase–lysosomal dysfunction, Gaucher / GBA1 -> Parkinson's ([ADR 0003](docs/adr/0003-demo-cluster-gaucher-gba1.md), seed list in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md))
- [x] Curated orgs and assets drafted in `data/curated/` (needs human check)
- [x] Ingest connectors for the slice: Monarch (MONDO/HGNC/OMIM-sourced links/HPO annotations/GO), HPO IC, ClinVar counts, ClinicalTrials.gov, curated YAML; cache committed in `data/cache/` (#15, #16, #17)
- [ ] PubMed ingest
- [ ] OpenAI Extract and Reconcile into evidence edges
- [x] `make data` / `make data-offline` build a validated, deterministic snapshot; the API loads it at startup and reports it in `/health` and `/api/v1/meta` (#33)

---

## License

[MIT](LICENSE)

Third-party data remains subject to its own license terms. See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

---

## Acknowledgements

- Hack-Nation for the 7th Global AI Hackathon
- OpenAI and the Buffalo Initiative for supporting Challenge 05
- MONDO, HPO, ClinVar, PubMed, OMIM, Orphanet, ClinicalTrials.gov, NIH RePORTER, and patient organizations whose public data this work builds on

Equilibrium is a research and hackathon prototype. It is not medical advice.
