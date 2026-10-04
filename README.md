# Equilibrium: AI atlas for rare diseases

We are building an evidence-first atlas that helps rare-disease communities move from fragmented information to actionable next steps.

[![CI](https://github.com/alijendoubi/equilibrium/actions/workflows/ci.yml/badge.svg)](https://github.com/alijendoubi/equilibrium/actions/workflows/ci.yml)
[![Security](https://github.com/alijendoubi/equilibrium/actions/workflows/security.yml/badge.svg)](https://github.com/alijendoubi/equilibrium/actions/workflows/security.yml)
[![Docker](https://github.com/alijendoubi/equilibrium/actions/workflows/docker.yml/badge.svg)](https://github.com/alijendoubi/equilibrium/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Team Equilibrium's submission to Hack-Nation's 7th Global AI Hackathon, Challenge 05: AI Atlas for the World's Rare Diseases, supported by OpenAI and the Buffalo Initiative.

> Status: early prototype. This README separates the product vision, the technical implementation, and the current roadmap status.

---

## Product overview

Rare diseases are often under-studied, poorly connected, and difficult to navigate for patients, caregivers, researchers, and biotech teams. Much of the knowledge is scattered across scientific papers, disease registries, trial data, funder databases, and patient organizations.

Equilibrium aims to turn that fragmented landscape into an evidence-backed knowledge graph that answers three practical questions:

1. Who shares our disease characteristics?
2. What useful work already exists?
3. What should we do together next?

The product is designed around a patient-organization leader, Maria, whose journey is:

```text
Search "disease X"
  -> disrupted mechanism (gene, variant effect, pathway)      [cited edge]
  -> another gene / related disease with the same mechanism    [cited edge]
  -> patient group working on that disease                     [cited edge]
  -> reusable asset: registry, natural history study, model    [cited edge]
  -> next step: sourced proposal + what needs expert review
```

This is not a generic “search engine.” It is a trustable map of relationships between disease mechanisms, genes, patient communities, and reusable assets.

### Who it serves

| Persona | Need | Planned experience |
|---|---|---|
| Maria, patient org leader | Clusters, shared assets, partners, next experiments | Cluster view, mechanism navigator, action view |
| Devon, newly diagnosed caregiver | Closest communities and relevant context in plain language | Global search with synonym resolution and explanation |
| Priya, biotech scout | Ranked clusters for one therapeutic mechanism | Mechanism-first cluster ranking |
| Dr. Osei, researcher | Who else works on a mechanism under different gene names | Connector view and network overlap |

### Design principles

- Evidence first: every claim is linked to a source and provenance record
- Honest gaps: if evidence is missing, the system shows what was searched and what is absent
- Explainability: graph paths become plain-language explanations with cited edges
- Actionability: the product surfaces next steps, not just literature connections

---

## Why this matters

- About 10,000 rare diseases are known.
- Roughly 80% are genetic, and around 5,000 are monogenic.
- Rare diseases affect about 350 million people worldwide.
- Fewer than 5% of rare diseases have an approved treatment.
- Relevant knowledge is spread across papers, disease databases, trials, funders, and patient communities.
- Disease names often hide the underlying mechanisms, which makes standard name-based search incomplete.

The 10x goal is simple: help research move toward a possible treatment 10x faster.

---

## What Equilibrium does

Equilibrium builds an evidence-backed knowledge graph that connects:

- disease entities and phenotypes
- genes, variants, and pathways
- related diseases with shared mechanisms
- patient organizations and communities
- registries, natural history studies, and model assets
- active trials, funding signals, and investigators
- action-oriented next steps backed by evidence

Every edge in the graph carries:

- source record or URL
- relation type
- confidence
- evidence type (observed, inferred, or curated)
- contradictory evidence when present

This keeps the graph useful without pretending that weak or unverified links are facts.

---

## Product architecture

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

### Technical flow

- Extract: OpenAI reads source text and pulls genes, variants, phenotypes, claims, and investigator entities into candidate edges.
- Reconcile: names and synonyms are normalized to stable IDs such as MONDO, HGNC, HP, ClinVar VCV, PMID, and NCT.
- Explain: a graph path is converted into plain-language reasoning, with every sentence backed by an edge ID.
- Trust layer: evidence confidence, contradictions, and missing-source reporting are tracked explicitly.

Detailed references:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/EVIDENCE_MODEL.md](docs/EVIDENCE_MODEL.md)
- [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)
- [docs/adr/](docs/adr/)

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
├── docs/                 architecture, evidence model, data sources, ADRs, runbook
├── scripts/github/       repo bootstrap scripts
├── .github/              workflows, rulesets, templates
├── docker-compose.yml
├── Makefile
├── README.md
├── .env.example
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
└── CODE_OF_CONDUCT.md
```

---

## Quickstart

Prerequisites:

- Python 3.12
- uv
- Node.js 20+
- pnpm
- GNU Make
- Docker (optional)

```bash
git clone https://github.com/alijendoubi/equilibrium.git
cd equilibrium
cp .env.example .env
make setup

make dev-backend
make dev-frontend
```

Or run both services with Docker:

```bash
docker compose up --build
```

Run `make help` to see all available targets. Common commands include:

```bash
make check   # lint, typecheck, tests, CI parity
make fmt     # format code
make clean   # clean generated artifacts
```

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Yes, for extract / reconcile / explain | OpenAI API access |
| `OPENAI_MODEL_EXTRACT` | No | Model for extract |
| `OPENAI_MODEL_EXPLAIN` | No | Model for explanation |
| `OPENAI_MODEL_RECONCILE` | No | Model for reconciliation |
| `OPENAI_EMBED_MODEL` | No | Embedding model |
| `NCBI_API_KEY` | No | Better PubMed / ClinVar rate limits |
| `OMIM_API_KEY` | No | OMIM access |
| `CORS_ORIGINS` | No | Allowed browser origins |
| `LOG_LEVEL` | No | Backend log level |
| `BACKEND_URL` | No | Server-side backend target |
| `NEXT_PUBLIC_API_URL` | No | Browser-side backend target |

---

## Data and evidence model

Equilibrium is designed to work with public sources and curated evidence rather than unverified model-generated claims.

### Planned data sources

| Source | Purpose | Access | Notes |
|---|---|---|---|
| MONDO | disease IDs and synonyms | OBO / JSON | disease taxonomy |
| HPO | phenotype and disease relations | annotation downloads | phenotype semantics |
| ClinVar | gene/variant/disease assertions | NCBI FTP / E-utilities | public data |
| OMIM | gene-phenotype associations | API | license terms apply |
| Orphanet | disease and patient resources | data downloads | public / attribution-based |
| PubMed / PMC | claims and investigators | NCBI APIs | abstracts subject to publisher rights |
| ClinicalTrials.gov | studies and interventions | API v2 | public |
| NIH RePORTER | funding and investigators | API v2 | public |
| Patient org directories | community and asset mapping | manual curation / site policies | per-site terms |

The project stores snapshots in `data/processed/` and keeps raw downloads under `data/raw/`. These folders are not committed.

The evidence model is documented in [docs/EVIDENCE_MODEL.md](docs/EVIDENCE_MODEL.md). See also [data/README.md](data/README.md).

---

## Status and roadmap

### Current status

Last updated: 2026-10-03

**Phase 1: Repo bootstrap (M1) — largely complete**

- [x] Challenge brief reviewed and documented
- [x] Monorepo scaffolding completed for backend and frontend
- [x] Architecture, evidence model, and project planning docs added
- [x] Rulesets for PRs, code owner approval, and required checks applied
- [x] Repo made public and security reporting enabled
- [ ] CI, security, and deployment workflows fully green on `main`
- [ ] Vercel and Render wired up with proper secrets

**Phase 2: Graph slice (M2) — not started**

- [x] Disease cluster selected: GBA1 / Gaucher / lysosomal dysfunction cluster
- [x] Curated organizations and asset notes drafted in `data/curated/`
- [ ] Ingest for MONDO, HPO, ClinVar, and PubMed in the slice
- [ ] OpenAI Extract and Reconcile into evidence edges
- [ ] `make data` reproduces a dated snapshot

**Phase 3: Trust layer (M3) — not started**

- Confidence scoring
- Contradiction tracking
- Coverage reporting
- Explain layer with edge citations

**Phase 4: UI journey (M4) — not started**

- Search
- Cluster view
- Edge explanation panel
- Patient action view

**Phase 5: Submission (M5) — not started**

See [docs/SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md).

### Project planning references

- [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)
- [docs/EXECUTION_PLAN.md](docs/EXECUTION_PLAN.md)
- [docs/RUNBOOK.md](docs/RUNBOOK.md)

---

## Development workflow

- Branches follow `feat|fix|docs|chore|data/<short-desc>` naming
- PR titles follow Conventional Commits because PRs are squash merged and the title becomes the commit message
- `main` is protected and requires PR review by the code owner (`@alijendoubi`)
- Required checks include backend, frontend, PR title validation, and secrets scanning

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [docs/RUNBOOK.md](docs/RUNBOOK.md).

---

## Team

| Name | Role | GitHub |
|---|---|---|
| Ali Jendoubi | Lead, code owner | [@alijendoubi](https://github.com/alijendoubi) |
| Khaled Md Saifullah | TBD | [@sagorhossain972](https://github.com/sagorhossain972) |
| Clara Hajj | TBD | [@clara578](https://github.com/clara578) |

---

## License

[MIT](LICENSE)

Third-party data remains subject to its own license terms. See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

---

## Acknowledgements

- Hack-Nation for the 7th Global AI Hackathon
- OpenAI and the Buffalo Initiative for supporting Challenge 05
- MONDO, HPO, ClinVar, PubMed / NCBI, OMIM, Orphanet, ClinicalTrials.gov, NIH RePORTER, and patient organizations for the public knowledge this work builds on

Equilibrium is a research and hackathon prototype. It is not medical advice.
