# Mock data (temporary)

**These files are mocks. The snapshot built by `make data` will replace them.**
They let us build the UI before the API is live (task B6, issue #23). Any node description
we have not checked against a source starts with `[MOCK]`. When mocks are on, every page shows a
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

## What is verified and what is a placeholder (checked 2026-10-03)

Checked against the source:

- MONDO ids and labels (EBI OLS): Gaucher disease `MONDO:0018150`, type II `MONDO:0009266`,
  type III `MONDO:0009267`, GBA1-related Parkinson disease `MONDO:1040030`, and Gaucher disease
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
