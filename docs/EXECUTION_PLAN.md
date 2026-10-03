# Execution Plan

This turns [PROJECT_PLAN.md](PROJECT_PLAN.md) into tasks the team can pick up. Every task has an ID, an owner, an estimate, its dependencies, a "done when" check and a GitHub issue.

- **T+0** is the hackathon start. Times are wall-clock hours from T+0.
- **Hero disease** means the cluster chosen in task A1 (#14): VAMP2/SNAREopathies or neuronopathic Gaucher/GBA1. Every task below works for either.
- **Owners:** `Ali`, `Sagor`, `Clara`. Sagor's and Clara's roles are proposed until confirmed in task A2. The fallback for a non-coder is in [PROJECT_PLAN 11.4](PROJECT_PLAN.md#114-workstreams-roles-for-sagor-and-clara-are-a-question-for-the-team).
- **Merge rule:** small PRs; `make check` must pass locally before asking for review (Actions are not running); Ali reviews in batches at each gate.

## Overview

| Phase | Window | Goal | Gate |
|---|---|---|---|
| A. Pre-kickoff | before T+0 | Decisions, accounts, keys | Everyone knows their first task |
| B. Foundations | T+0 to T+3 | Evidence model, OpenAI access, seeds, UI skeleton | **G1**: cluster locked, P0 sources reachable, OpenAI calls working |
| C. Graph slice | T+3 to T+8 | Real data in a queryable graph; first deploy | **G2**: search, node, neighbors and path work on real data |
| D. Trust + intelligence | T+8 to T+14 | Trust layer, clustering, Explain, actions | **G3**: golden path and gap report come back from the API |
| E. Journey + polish | T+14 to T+20 | End-to-end UI on the deployed URL, fallbacks | **G4** at T+18; **feature freeze** at T+20 |
| F. Submission | T+20 to T+24 | Videos, checklist, submit | **Submit** at T+23.5 |

Critical path: `A1 -> B1 -> B4/C1 -> C5 -> C8 -> D6 -> D7 -> E1 -> F1`. The demo does not wait on AI extraction (C3), because the golden path is built from curated and observed edges.

---

## Phase A: Pre-kickoff

| ID | Task | Owner | Est. | Depends | Done when | Issue |
|---|---|---|---|---|---|---|
| A1 | Choose the cluster: SNAREopathies or Gaucher/GBA1. Write ADR 0003 and the seed list (MONDO / HGNC IDs) | Ali + team | 0.5 h | none | ADR merged; seeds in DATA_SOURCES.md | #14 |
| A2 | Confirm roles and skills for Sagor and Clara | Ali | 15 min | none | Owners column below confirmed | none |
| A3 | Confirm hackathon rules: start time, timezone, whether pre-work is allowed, submission format | Ali | 15 min | none | Noted in README Status | none |
| A4 | OpenAI: create a project key, set a $50 spend cap, add the `OPENAI_API_KEY` repo secret and local `.env` | Ali | 15 min | none | Key works in the B2 smoke test | #31 |
| A5 | Create the Vercel and Render projects; set `VERCEL_*` and `RENDER_DEPLOY_HOOK_URL` secrets (docs/RUNBOOK.md) | Ali | 30 min | none | Secrets listed by `gh secret list` | #25 |
| A6 | Merge the plan PR (#29); both teammates accept invites and read PROJECT_PLAN sections 1, 3 and 12 | All | 20 min | none | Everyone has repo access | none |

## Phase B: Foundations (T+0 to T+3) -> G1

| ID | Task | Owner | Est. | Depends | Done when | Issue |
|---|---|---|---|---|---|---|
| B1 | Evidence model v2: edge ids, provenance fields, qualifiers, URL rule | Ali | 1 h | A1 | Models + EVIDENCE_MODEL.md updated together; tests green | #30 |
| B2 | OpenAI config split + smoke test (Sol, Luna structured outputs, embeddings, one Batch submit) | Ali | 1 h | A4 | Smoke passes or fallback model documented | #31 |
| B3 | Verify every seed entity (IDs resolve, no approved therapy for the hero, patient orgs exist or not) | Sagor | 1 h | A1 | Each `[U]` for the chosen cluster is now `[V]` or removed | #14 |
| B4 | Ingest diseases, phenotypes and synonyms via the Monarch API + `phenotype.hpoa` (whole-file IC) | Sagor | 2.5 h | B1 | Raw JSON committed; nodes + `has_phenotype` edges carry provenance | #15 |
| B5 | Curate patient orgs, registries and assets into `data/curated/*.yaml` | Clara | 1.5 h | A1 | At least 5 orgs and 6 assets with URL + date; orgless diseases listed | #32 |
| B6 | UI skeleton on mock JSON: home with search, disease page | Clara | 2 h | none | Renders locally; `pnpm` checks green | #23 |
| B7 | No-other-LLM-provider guard test | Ali | 20 min | none | Test in suite and passing | #34 |

**G1 at T+3:** cluster locked, P0 sources reachable, seeds verified, OpenAI calls working. If a P0 source fails, switch to its fallback in PROJECT_PLAN section 5.

## Phase C: Graph slice (T+3 to T+8) -> G2

| ID | Task | Owner | Est. | Depends | Done when | Issue |
|---|---|---|---|---|---|---|
| C1 | Gene-disease links (Monarch, OMIM-sourced), GO mechanism annotations, ClinVar counts | Sagor | 2 h | B1, B4 | `caused_by` and `participates_in` edges with provenance | #16 |
| C2 | ClinicalTrials.gov studies for the seeds (API v2) + link curated assets | Sagor | 1.5 h | B1, B5 | `studies_condition` edges; the reusable asset for the hero is present | #17 |
| C3 | PubMed corpus fetch (300-600 abstracts) and submit the Extract Batch job | Ali | 2 h | B2 | Batch submitted; results cached when they return | #18 |
| C4 | Reconcile: exact match + embeddings; Luna only for ambiguous cases | Ali | 2 h | B2, B4 | One stable node per entity; synonym search works | #19 |
| C5 | Pipeline orchestrator + snapshot loader (`make data`, `make data-offline`) | Sagor | 2 h | C1, C2 | Clean clone gives an identical snapshot hash; API loads it | #33 |
| C6 | Smoke deploy: frontend to Vercel, backend to Render | Ali | 1 h | A5 | Both URLs live with `/health` green | #25 |
| C7 | Path view + edge evidence panel on mock data | Clara | 3 h | B6 | Chain of chips; side panel shows source, date, confidence | #24 |
| C8 | API: `search`, `nodes/{id}`, `neighbors`, `paths` on the real snapshot | Ali | 2 h | C5 | Endpoints answer in under 50 ms with tests | #22 |

**G2 at T+8:** search, node, neighbors and path work on real data. If behind: drop RePORTER (D3) and Reactome, and cap Extract at 150 abstracts.

## Phase D: Trust and intelligence (T+8 to T+14) -> G3

| ID | Task | Owner | Est. | Depends | Done when | Issue |
|---|---|---|---|---|---|---|
| D1 | Trust layer: confidence rubric with reasons, contradictions, coverage report | Ali | 2.5 h | C5 | Every edge has a confidence and reasons; coverage report for any node | #21 |
| D2 | Clustering: IC-weighted phenotype similarity + GO mechanism overlap, Louvain, bridges, counterexamples | Sagor | 3 h | C1, C5 | `clusters` endpoint returns members, features and at least 1 counterexample | #20 |
| D3 | RePORTER investigators + shared-investigator bridges (P1, cut first) | Sagor | 2 h | C5 | At least 1 bridge or an explicit "none found" | #38 |
| D4 | Merge Extract results with verbatim-quote check; label 30-abstract gold set; eval script | Ali (+Sagor labelling) | 2.5 h | C3 | Precision/recall stored in the manifest | #35 |
| D5 | Explain: edge-id validator, cache, template fallback, offline mode | Ali | 2.5 h | C8, D1 | With no key set, demo screens show cited explanations | #36 |
| D6 | Actions endpoint: partners, assets, what differs, next experiment, or coverage | Ali | 1.5 h | D1, C2 | Hero returns org + study + differences; gap disease returns coverage | #37 |
| D7 | Wire the UI to the live API; build the action view and gap card | Clara | 4 h | C7, C8, D6 | Golden and gap journeys work against the API locally | #24 |

**G3 at T+14:** the golden path and the gap report come back from the API. If behind: Explain runs only on precomputed demo paths, the cluster view becomes a list, and the Priya view is dropped.

## Phase E: Journey and polish (T+14 to T+20) -> G4, freeze

| ID | Task | Owner | Est. | Depends | Done when | Issue |
|---|---|---|---|---|---|---|
| E1 | Precompute Explain for the demo paths; commit the cache | Ali | 1 h | D5 | Cache hit for every demo path | #36 |
| E2 | Frontend static demo fallback | Clara | 1.5 h | D7 | Full video flow works with the backend stopped | #39 |
| E3 | Built with OpenAI: README section, "AI-generated" labels, `/meta` usage stats | Ali + Clara | 1.5 h | D5 | All three visible; numbers from the manifest | #40 |
| E4 | Cluster visualization (should-have; skip if G3 was late) | Clara | 2 h | D2, D7 | Small force graph with dashed bridges | #23 |
| E5 | Verify every edge link shown in the demo (10+ spot checks) | Sagor | 1 h | D7 | Every demo edge opens a working source URL | none |
| E6 | Clean-clone reproduction test of `make data-offline` and `docker compose up` | Sagor | 1 h | C5 | Works on a fresh clone; README steps accurate | #33 |
| E7 | Final `make data`, deploy, switch Render to a paid always-on instance, warm-up | Ali | 1 h | E1-E3 | Deployed URL runs the full journey | #25 |

**G4 at T+18:** the full UI journey (golden + gap) works on the deployed URL. If behind: record from local `docker compose` and keep the deployed URL as best effort with the static fallback. **T+20: feature freeze.** Only fixes after this.

## Phase F: Submission (T+20 to T+24)

| ID | Task | Owner | Est. | Depends | Done when | Issue |
|---|---|---|---|---|---|---|
| F1 | 10x moonshot narrative, team video and 1-minute walkthrough (DEMO_SCRIPT.md) | Clara (narrate) + Ali (drive) | 2.5 h | G4 | Both videos uploaded and linked in README | #26 |
| F2 | Submission checklist: README Status, placeholders removed, links tested in a private window | Ali | 1 h | F1 | Every item in SUBMISSION_CHECKLIST.md ticked | #27 |
| F3 | Submit at T+23.5 (30 min buffer); tag `v1.0.0` | Ali | 15 min | F2 | Submission confirmed | #27 |
| F4 | After judging: rotate the OpenAI, Vercel and Render keys | Ali | 15 min | F3 | Old keys revoked | #27 |

---

## Load per person

| Person | Phase B | Phase C | Phase D | Phase E | Phase F |
|---|---|---|---|---|---|
| Ali | B1, B2, B7 | C3, C4, C6, C8 | D1, D4, D5, D6 | E1, E3, E7 | F1, F2, F3, F4 |
| Sagor | B3, B4 | C1, C2, C5 | D2, D3, D4 (labelling) | E5, E6 | docs pass |
| Clara | B5, B6 | C7 | D7 | E2, E3, E4 | F1 |

Sleep rotation: each person gets 3-4 hours between T+10 and T+18, staggered so one coder is always awake.
