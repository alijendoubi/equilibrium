# data/

These are the conventions for building and storing the atlas dataset.

Status: **conventions only**. The pipeline (`make data`) is Phase 2 and does not exist yet. See [docs/DATA_SOURCES.md](../docs/DATA_SOURCES.md) and [docs/EVIDENCE_MODEL.md](../docs/EVIDENCE_MODEL.md).

## Layout

```text
data/
├── README.md          this file (committed)
├── scripts/           dataset build scripts (committed)
├── curated/           hand-curated orgs, assets, mechanisms, condition aliases (committed)
├── cache/             compact source payloads for the slice (committed, < 5 MB)
│   └── <source>/payload.json
├── raw/               downloaded source records (NOT committed)
│   └── <source>/<YYYY-MM-DD>/...
└── processed/         built snapshots (NOT committed)
    └── atlas-<cluster>-<YYYY-MM-DD>[-<n>]/
        ├── nodes.parquet      (or nodes.json)
        ├── edges.parquet      (or edges.json)
        ├── clusters.json
        └── manifest.json
```

- `cache/` is committed. Each `payload.json` holds only the fields the normalizers need, plus `meta` (`url`, `source_version`, `retrieved_at`). Refresh it online with `cd backend && uv run python -m atlas.ingest fetch [--source monarch|hpo|go|clinvar|clinicaltrials]`. The HPO step downloads `phenotype.hpoa` and `hp.obo` (about 47 MB) to `raw/hpo/` and commits only the IC map for slice phenotypes.
- `raw/` and `processed/` are gitignored. Raw dumps can be large, and some sources (for example OMIM) restrict redistribution.
- `scripts/` is committed. Everything in `processed/` must be reproducible from `scripts/`, the backend packages and the public sources.
- Never put patient-identifying data anywhere under `data/`. See [SECURITY.md](../SECURITY.md).

## Snapshot naming

`atlas-<cluster-slug>-<YYYY-MM-DD>[-<n>]`, for example `atlas-lsd-2026-10-04` or `atlas-lsd-2026-10-04-2`.

- The date is the UTC build date.
- Add the `-<n>` suffix when the same cluster is rebuilt more than once on the same day.

The backend serves the snapshot named in its config. `GET /api/v1/meta` reports which snapshot is loaded (planned).

## Provenance manifest

Every snapshot includes a `manifest.json`:

```json
{
  "snapshot_id": "atlas-lsd-2026-10-04",
  "built_at": "2026-10-04T09:00:00Z",
  "git_commit": "<sha>",
  "cluster": {"slug": "lsd", "seed_ids": ["MONDO:..."]},
  "sources": [
    {
      "source": "clinvar",
      "version": "2026-09",
      "retrieved_at": "2026-10-04T08:12:00Z",
      "url": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/",
      "license": "public domain (NCBI)",
      "records": 1234
    }
  ],
  "llm": {"model": "gpt-4.1-mini", "prompt_versions": {"extract": "v1", "reconcile": "v1", "explain": "v1"}},
  "rubric_version": "v1",
  "counts": {"nodes": 0, "edges": 0, "edges_by_evidence_type": {"observed": 0, "curated": 0, "inferred": 0}},
  "rejected": {"extract_no_quote": 0, "reconcile_no_match": 0}
}
```

The manifest also feeds the honest-gap coverage report: a source missing from `sources` was not searched.

## Reproducing (planned)

```bash
cp .env.example .env    # OPENAI_API_KEY; NCBI_API_KEY recommended
make data               # PLANNED: ingest -> extract/reconcile -> graph -> snapshot
```

LLM outputs can vary between runs. The pipeline caches every OpenAI response by input hash under `data/raw/_llm_cache/`, so a rebuild from the same cache is deterministic.
