# Contributing to Equilibrium

This repo is built in a 24-hour hackathon. These rules exist to keep `main` demoable at all times. They are not meant to slow anyone down.

## TL;DR

1. Pick an issue and assign it to yourself.
2. Create a branch: `git switch -c feat/edge-panel`
3. Open a **draft PR** early.
4. Run `make check` locally until it passes.
5. Give the PR a Conventional Commit title and get 1 approval.
6. Squash merge.

## Branch naming

```text
<type>/<short-desc>
```

| Type | Use for |
|---|---|
| `feat/` | New user-visible capability |
| `fix/` | Bug fix |
| `docs/` | Documentation only |
| `chore/` | Tooling, CI, deps, repo config |
| `data/` | New or changed data source, ingest or snapshot logic |
| `refactor/`, `test/`, `perf/`, `ci/` | Optional, finer-grained prefixes that match the PR title types |

Use kebab-case and keep it short, for example `feat/cluster-view`, `data/clinvar-ingest` or `fix/cors-origins`.

## PR titles (Conventional Commits)

`main` is **squash-merge only**, so the PR title becomes the commit message on `main`. The `pr-title` check enforces this format:

```text
<type>(<optional scope>): <imperative summary>
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `ci`, `build`, `revert`. Suggested scopes: `api`, `graph`, `ingest`, `extract`, `models`, `ui`, `data`, `ci`.

Examples:
- `feat(graph): add IC-weighted HPO similarity`
- `fix(api): return 404 for unknown node id`
- `docs: add honest-gap section to evidence model`

## PR flow

1. Sync with `main`: `git switch main && git pull --ff-only`
2. Create a branch: `git switch -c feat/<short-desc>`
3. Commit freely on the branch. Commits are squashed on merge.
4. Push and open a **draft PR** right away: `gh pr create --draft --fill`
5. Fill in the PR template: what changed, how it was tested, and screenshots for UI changes. Link the issue with `Closes #N`.
6. When `make check` passes locally, mark the PR ready: `gh pr ready`
7. Request 1 reviewer. Approvals are dismissed when new commits are pushed.
8. Resolve all review threads.
9. When required checks are green, **squash merge**: `gh pr merge --squash --delete-branch`

Keep PRs small, **under 400 changed lines** excluding lockfiles and generated files. The `size/*` label is applied automatically. Split anything labelled `size/XL`.

## Required checks

| Check | Workflow | Run locally |
|---|---|---|
| `backend` | `ci.yml` | `make lint typecheck test` (backend part) |
| `frontend` | `ci.yml` | `make lint typecheck test` (frontend part) |
| `pr-title` | `pr-hygiene.yml` | Check the title against the format above |
| `secrets-scan` | `security.yml` (gitleaks) | `pre-commit run --all-files` |

`make check` runs lint, typecheck and tests for both apps, the same as CI. Other workflows are informational:
- CodeQL and dependency audit
- Docker image build
- Vercel and Render preview deploys
- E2E tests, which run only when the PR has the `run-e2e` label

## Pre-commit

```bash
uv tool install pre-commit    # or: pipx install pre-commit
pre-commit install
pre-commit run --all-files    # first run
```

Hooks run formatters and a gitleaks secret scan before each commit. Do not bypass them with `--no-verify`. If a hook is wrong, fix the hook in a `chore/` PR.

## Definition of done

A PR is done when:

- [ ] `make check` passes and CI is green
- [ ] New behavior has tests. Backend coverage stays **at or above 80%**.
- [ ] Docs are updated where behavior changed: `docs/`, API notes, `.env.example`
- [ ] The README **Status** section is updated in the same PR when the change moves a milestone
- [ ] Data changes record provenance. Every new edge carries `provenance{source, source_record_id, url, retrieved_at}`, a `confidence` and an `evidence_type`. See [docs/EVIDENCE_MODEL.md](docs/EVIDENCE_MODEL.md).
- [ ] No secrets, no patient PII, no restricted-license data committed. See [SECURITY.md](SECURITY.md).

## Adding a data source

1. Open an issue using the **data source** template, labelled `type:data` and `module:graph-builder`. State the source, URL, access method, license or terms, and which edge types it feeds.
2. Add a row to [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) in the same PR as the code. Mark the license as "verify" until someone has actually read the terms.
3. Implement a connector in `backend/atlas/ingest/`:
   - Fetch into `data/raw/<source>/<YYYY-MM-DD>/`.
   - Respect rate limits and API keys from env.
   - Record the source version and retrieval time.
4. Map records to `Node` and `Edge` objects. Each edge must carry provenance that points to the specific source record, not just the database.
5. Add tests that use a small fixture. Tests must not depend on network access.
6. Add the source to the provenance manifest and to the coverage report, so honest-gap answers list it as "searched". See [data/README.md](data/README.md).

## Emergency hotfix policy

Admin bypass of the ruleset is allowed **only** when the deployed demo is broken during a judging-critical window and normal review would take too long. When it is used:

1. Make the smallest possible fix on a `fix/` branch, push it and merge it with admin rights.
2. Post in the team channel what was bypassed and why.
3. Within 2 hours, open a follow-up PR for review that adds tests or a cleanup, labelled `priority:P0`.

Never bypass for convenience, and never force-push `main`.

## Labels

| Group | Labels | Meaning |
|---|---|---|
| Type | `type:*` (feat, bug, docs, chore, data) | Kind of work |
| Area | `area:*` (backend, frontend, infra, data, docs) | Where the change lives |
| Priority | `priority:P0`, `priority:P1`, `priority:P2` | P0 = demo-blocking, P1 = needed for submission, P2 = nice to have |
| Module | `module:graph-builder`, `module:trust`, `module:action`, `module:ux` | Brief module the work serves |
| Size | `size/*` | Applied automatically from the diff size |
| CI | `run-e2e` | Triggers the Playwright E2E workflow |

## Milestones

| Milestone | Scope |
|---|---|
| M1 Repo ready | Scaffold, CI, rulesets, deploy targets |
| M2 Graph slice | One disease cluster ingested, Extract and Reconcile, `make data` |
| M3 Trust layer | Confidence, contradictions, coverage and honest gaps, Explain with edge citations |
| M4 UI journey | Search, cluster view, edge panel, patient action view |
| M5 Submission | Deployed prototype, README, videos, go-public |

## 24-hour working agreements

- **Sync cadence:** a 10-minute stand-up every 4 hours covering what is done, what is next and what is blocked. Post blockers in the team channel immediately instead of waiting for the next stand-up.
- **Claim before you code:** assign the issue to yourself. If nothing exists, open an issue first. Unassign if you drop it.
- **Draft PRs early:** opening a PR in the first 30 minutes of work makes progress visible and surfaces conflicts.
- **Reviews are fast:** a review request gets a response within 30 minutes. Review the smallest PRs first.
- **`main` is always demoable.** Put risky work behind a flag or keep it in a branch.
- **Freeze:** feature freeze 3 hours before the deadline. After that, only P0 fixes, docs and the video.
- **Honesty over polish:** never fake a feature in the demo. Label anything planned as planned.

## Code of conduct

Participation is covered by our [Code of Conduct](CODE_OF_CONDUCT.md).
