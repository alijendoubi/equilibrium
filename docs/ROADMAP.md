# Roadmap

The plan for Equilibrium from today to a multi-cluster atlas. Every task has an owner lane, its
dependencies and a testable "done when". GitHub issues are the task board (see
[AGENTS.md](../AGENTS.md)); this file is the map that ties them together. Review it at the start
of each milestone.

## Where we are (2026-10-09)

- **Product:** one slice (GBA1/GCase–lysosomal, Gaucher ↔ Parkinson's): 832 nodes and 1,498
  edges (977 curated, 521 observed, **0 inferred**), deployed on Vercel (frontend) and Render
  (API). Journey: orb home → search → disease → evidence map → path → actions.
- **AI:** Reconcile, Explain and Extract are implemented and tested with mocked clients, but no
  OpenAI output has been generated yet (no credits), so search is lexical and briefs use the cited
  template.
- **Quality:** backend 471 tests (98.5% coverage, `mypy --strict`), frontend 149 unit tests and
  6 Playwright journeys, axe sweep with 0 findings.
- **Blocker:** GitHub Actions are billing-locked, so CI and the deploy workflow do not run and
  every merge is an admin bypass after local gates.

## Who does what

| Lane | Owns | Never does |
|---|---|---|
| **Owner** (@alijendoubi) | Decisions, secrets and billing, merges, human data review, outreach | - |
| **Claude Code** | `frontend/**`, `docs/**`, `README.md`, `AGENTS.md`, reviews of Codex PRs | Backend, data, CI or deploy files |
| **Codex** | `backend/**`, `data/**`, `scripts/**`, `.github/**`, `render.yaml`, Dockerfiles | Frontend or docs files |

Cross-lane work is split into a contract issue and one PR per lane (backend first). Neither agent
merges.

## Milestones

| Milestone | Goal | Exit criteria |
|---|---|---|
| **v0 Foundations** | Unblock the project | CI green, PR queue merged, keys rotated, F4 decisions recorded |
| **v1.0 Public launch** | A trustworthy public release | Launch checklist #69 complete, `v1.0.0` tagged |
| **v1.1 Evidence quality** | Measured, human-verified evidence | Gold-set precision/recall published; curated data verified; real AI output shipped |
| **v1.2 Product depth** | Make the journey shareable and fast | Briefs shareable/printable, guided first run, perf budget enforced |
| **v2.0 Second cluster** | Prove the atlas generalises | Two slices in one snapshot, cross-slice search, storage decision recorded |

Work proceeds in milestone order. Inside a milestone, take the first unblocked task in your lane
in the order listed.

## v0 Foundations

| ID | Task | Lane | Depends | Done when | Issue |
|---|---|---|---|---|---|
| F1 | Resolve the billing lock; CI green on `main` | Owner | - | `ci`, `security`, `e2e` pass on a PR; admin bypass no longer needed | #79 |
| F2 | Merge the open PR queue in order: #67 → #72 → #77; #66 (after fixes) → #78; Codex PRs #71, #74, #76 after their review fixes | Owner | reviews | No open PR older than its review | - |
| F3 | Prune stale worktrees and merged branches | Claude Code | owner OK | Only active worktrees left; nothing unpushed lost | #80 |
| F4 | Name, domains, licence, team access | Owner | - | ADR 0004 records them | #81 |
| F5 | Rotate every hackathon-era key | Owner | - | New OpenAI, Vercel, Render, NCBI keys set; old ones revoked | #69 |

## v1.0 Public launch

| ID | Task | Lane | Depends | Done when | Issue |
|---|---|---|---|---|---|
| L1 | Deploy config verified end to end (keep Render `autoDeploy` until the hook is proven) | Codex + Owner secrets | F1, F5 | A PR gets a preview; a merge reaches production on both hosts | #25, #74 |
| L2 | Rate limiting keyed on the real visitor + stable error envelope | Codex | - | Spoofing and shared-IP cases from the #76 review covered by tests; `mypy --strict` clean | #75, #76 |
| L3 | Frontend forwards the visitor IP with a shared-secret header | Claude Code | L2 contract | Both headers sent from server components and the trace action; token server-only | #82 |
| L4 | `/api/v1/meta` exposes `openai_usage` | Codex | - | Read from the manifest, with a test | #40 |
| L5 | Marketing homepage on its subdomain | Owner (#66), Claude Code (#78 docs) | F4 domain | Review items on #66 fixed; env vars documented | #66, #73 |
| L6 | Security headers and CSP | Claude Code | - | CSP without `unsafe-eval`, HSTS and friends; e2e green with CSP on | #83 |
| L7 | About, disclaimer, privacy, terms pages | Claude Code, owner approves | F4 | Linked from every footer; wording signed off | #84 |
| L8 | Sitemap, metadata, Open Graph images | Claude Code | F4 domain | Every route titled; dynamic OG for diseases; canonical URLs | #85 |
| L9a | Request ids, structured logs, optional error tracking (API) | Codex | - | `X-Request-ID` on every response; JSON logs; DSN-gated | #86 |
| L9b | Error boundaries and client error reporting | Claude Code | L9a convention | Friendly retry UI with request id; DSN-gated | #87 |
| L10 | Privacy-friendly analytics (or none) | Owner decides, Claude Code builds | F4 | Cookieless, documented on `/privacy`, env-gated | #88 |
| L11 | Post-deploy live smoke + uptime check | Codex (workflow), Claude Code (specs) | F1, L1 | Live Playwright after each deploy; `/health` checked every 10 min | #89 |
| L12 | Release process, CHANGELOG, `v1.0.0` | Codex (workflow), Claude Code (notes) | all of v1.0 | Tag published with notes; checklist #69 ticked | #90 |

Already in review for v1.0: #72 (hackathon framing removed), #77 (accessibility pass), #78
(marketing env docs).

## v1.1 Evidence quality

| ID | Task | Lane | Depends | Done when | Issue |
|---|---|---|---|---|---|
| Q1 | Human verification of curated organisations, assets and contradictions | Owner (+ domain expert) | - | No entry left with `needs human check` | #32 |
| Q2 | Curated-record schema validation | Codex | - | #71 review fixes in; malformed records fail with clear errors | #71 |
| Q3 | Hand-label the 30-abstract gold set | Owner | - | `data/eval/gold_claims.jsonl` covers 30 PMIDs, human-labelled | #35 |
| Q4 | Eval scores into the manifest; README cites them | Codex, then Claude Code | Q3, Q5 | Precision/recall/F1 in `manifest.json` and the README | #35 |
| Q5 | Precompute OpenAI caches; publish real usage | Owner (credits), Codex (run) | F5 | `openai_usage.calls > 0`; offline rebuild still byte-identical | #91 |
| Q6 | Surface semantic matches and AI briefs in the UI | Claude Code | Q5 | Both AI and template states tested and labelled | #92 |
| Q7 | Scheduled snapshot refresh with a diff-report PR | Codex | F1 | Monthly PR only when data changes, with a change summary | #93 |
| Q8 | Source freshness on edges and pages | Codex (field), then Claude Code (UI) | - | "Retrieved N days ago"; >180 days flagged | #94 |
| Q9 | "Report a problem" on an edge | Claude Code (UI), Codex (issue form) | - | Prefilled GitHub issue form; no accounts, no PII | #95 |

## v1.2 Product depth (issues opened when v1.1 closes)

| ID | Task | Lane | Done when |
|---|---|---|---|
| P1 | Evidence skyline / confidence profile view (owner branch `feat/map-evidence-skyline`) | Owner builds, Claude Code reviews and polishes | Merged with tests, a11y sweep clean |
| P2 | Shareable, printable collaboration brief | Claude Code | Print stylesheet, copy-link, brief URL restores the same path |
| P3 | Dynamic share images per disease and path | Claude Code | OG image shows the disease and its strongest sourced link |
| P4 | Guided first run (Maria's journey) | Claude Code | Skippable walkthrough; never blocks keyboard or screen reader users |
| P5 | Public API docs and versioning policy | Codex | OpenAPI descriptions and examples for every route; `/api/v1` stability policy in docs |
| P6 | Performance budget | Codex (Lighthouse CI), Claude Code (fixes) | LCP < 2.5 s on key routes; `/api/v1/graph` p95 < 300 ms on the slice |

## v2.0 Second cluster (issues opened when v1.2 closes)

| ID | Task | Lane | Done when |
|---|---|---|---|
| S1 | Choose the second cluster (candidate: presynaptic SNAREopathies, the documented fallback in ADR 0003) | Owner decides, Claude Code drafts the ADR | ADR accepted |
| S2 | Multi-slice pipeline: per-slice config and curated seeds, one snapshot | Codex | Two slices build deterministically; existing slice unchanged byte for byte |
| S3 | Slice switcher and cross-slice search | Claude Code | Search and map work across slices; URLs carry the slice |
| S4 | Storage decision: in-memory networkx vs a graph database | Codex | Load test at 10× nodes; ADR records the choice and the threshold |
| S5 | Community curation: contribution guide and schema CI for curated YAML | Claude Code (guide), Codex (CI) | An outside contributor can add an organisation through a validated PR |

## Ongoing (owner)

- **Expert review:** a Gaucher clinician and a Parkinson's trialist review the hero path and the
  brief before any outreach claims.
- **Partnerships:** the International Gaucher Alliance and the ASPro-PD team (does it collect GCase
  or glucosylsphingosine data?).
- **Funding and governance:** grants, a maintainer list in `CODEOWNERS`, and a quarterly roadmap
  review that updates this file.

## Rules that do not change

- Every edge shown is a sourced claim; inferred edges stay dashed and capped below curated
  confidence; contradictions are shown, not hidden; a missing answer is an honest gap.
- No patient data, no accounts, research context only.
- Local gates pass before every PR (see [AGENTS.md](../AGENTS.md#definition-of-done)).
