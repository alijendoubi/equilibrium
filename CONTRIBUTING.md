# Contributing to Equilibrium

These rules keep `main` releasable at all times. They are not meant to slow anyone down. Coding agents (Claude Code, Codex) also follow [AGENTS.md](AGENTS.md).

## TL;DR

1. Pick an issue and assign it to yourself.
2. Create a branch: `git switch -c feat/edge-panel`
3. Open a **draft PR** early.
4. Run `make check` locally until it passes.
5. Give the PR a Conventional Commit title and get approval from @alijendoubi (the only code owner; only his approval can merge).
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
7. Request review from @alijendoubi (the code owner). Only his approval counts toward merge, and it must come after the last push: approvals are dismissed when new commits are pushed.
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

Admin bypass of the ruleset is allowed **only** in two cases: the deployed app is broken and normal review would take too long, or CI cannot run at all (as now, while GitHub Actions is billing-locked). When it is used:

1. Run every gate locally first (see [AGENTS.md](AGENTS.md#definition-of-done)) and paste the results into the PR.
2. Keep the change small; for an outage, use a `fix/` branch with the smallest possible fix.
3. Say in the PR what was bypassed and why. For an outage fix, open a follow-up PR with tests or cleanup within a day, labelled `priority:P0`.

Never bypass for convenience, and never force-push `main`.

## Labels

| Group | Labels | Meaning |
|---|---|---|
| Type | `type:*` (feat, bug, docs, chore, data) | Kind of work |
| Area | `area:*` (backend, frontend, infra, data, docs) | Where the change lives |
| Priority | `priority:P0`, `priority:P1`, `priority:P2` | P0 = blocks the next release, P1 = planned for the current milestone, P2 = nice to have |
| Module | `module:graph-builder`, `module:trust`, `module:action`, `module:ux` | Brief module the work serves |
| Size | `size/*` | Applied automatically from the diff size |
| CI | `run-e2e` | Triggers the Playwright E2E workflow |

## Milestones

| Milestone | Scope |
|---|---|
| v1.0 Public launch | Deployed, keys rotated, hackathon framing removed, tagged `v1.0.0` |
| v1.1 Evidence quality | Human-verified curated data, measured extraction quality |

The hackathon milestones (M1 to M5) are closed and kept for history.

## Working agreements

- **Blockers go on the issue:** comment on the issue as soon as you are blocked, and add `blocked:owner` when only the maintainer can unblock it.
- **Claim before you code:** assign the issue to yourself. If nothing exists, open an issue first. Unassign if you drop it.
- **Draft PRs early:** an early draft PR makes progress visible and surfaces conflicts.
- **Small PRs, fast reviews:** review the smallest PRs first.
- **`main` is always releasable.** Put risky work behind a flag or keep it in a branch.
- **Honesty over polish:** never fake a feature. Label anything planned as planned.

## Code of conduct

Participation is covered by our [Code of Conduct](CODE_OF_CONDUCT.md).
