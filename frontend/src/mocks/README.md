# Mock data (temporary)

**These files are mocks. The snapshot built by `make data` will replace them.**
They let us build the UI before the API is live (task B6, issue #23). Any node description
(`attributes.description`) we have not checked against a source starts with `[MOCK]`. When mocks are on, every page shows a
"Mock data" banner.

| File            | Shape                                                                                     | Mirrors                            |
| --------------- | ----------------------------------------------------------------------------------------- | ---------------------------------- |
| `nodes.json`    | `AtlasNode[]`                                                                             | `GET /api/v1/nodes/{id}` -> `node` |
| `edges.json`    | `Edge[]`. Each edge has a source URL, or `source: "analytics"` plus `supporting_edge_ids` | `GET /api/v1/edges/{id}`           |
| `paths.json`    | demo paths stored as node and edge ids. The mock client fills them in and slices them     | `GET /api/v1/paths`                |
| `actions.json`  | the action view for each disease, as node and edge ids                                    | `GET /api/v1/actions/{disease_id}` |
| `coverage.json` | `CoverageReport[]`                                                                        | `GET /api/v1/coverage/{node_id}`   |

When the mock client loads (`src/lib/api/mock-data.ts`), zod validates every file. It also checks
referential integrity: each edge endpoint and each referenced id must exist.

## Id formats (match backend `evidence.py`, PR #41)

- Node ids are CURIEs. Trials are `clinicaltrials:NCT05778617`; the UI shows `NCT05778617`.
- Edge ids are `E:` + 16 lowercase hex, computed exactly like the backend's `compute_edge_id`:
  `sha256(json.dumps([source_id, relation, target_id, provenance.source, source_record_id],
separators=(",", ":")))[:16]`. If you change one of those five fields, recompute the id.
- `attributes` and `qualifiers` are `str -> str` maps, so numbers such as `ic` are strings.
- Node descriptions live in `attributes.description`. The backend `Node` has no `description` field.
- On 2026-10-04 the backend `Node` and `Edge` pydantic models (branch `feat/evidence-model-v2`)
  accepted all 20 nodes and 25 edges, and every edge id matched its content.

## What is verified and what is a placeholder (checked 2026-10-03)

Checked against the source:

- MONDO ids and labels (EBI OLS): Gaucher disease `MONDO:0018150`, type II `MONDO:0009266`,
  type III `MONDO:0009267`, late-onset Parkinson disease `MONDO:0008199` (the id used by the real snapshot), and Gaucher disease
  due to saposin C deficiency `MONDO:0012517`.
- HGNC: GBA1 `HGNC:4177` and PSAP `HGNC:9498`. HPO and GO term ids and labels.
- ASPro-PD `NCT05778617` (ClinicalTrials.gov API v2): phase 3, recruiting, 330 estimated,
  ambroxol 420 mg, listed condition "Parkinson Disease", and the eligibility quote on GBA1 status.
- Narita et al. 2016, `PMID:27042680` (PubMed): the title and the two quoted abstract sentences.
- Cure Parkinson's funds ASPro-PD (cureparkinsons.org.uk, January 2023 announcement).

Placeholders (do not cite):

- All `confidence` values and `confidence_reasons`. They show what rubric r1 looks like; nothing
  computed them.
- Phenotype `ic` values, and which HPO terms are annotated to which disease.
- The coverage counts for saposin C deficiency (`source_version: "MOCK"`).
- The partner and asset wording in `actions.json`, and the next experiment.
