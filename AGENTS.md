# Equilibrium: agent working agreement (Claude Code + Codex)

Two coding agents work on this repo in parallel. Read this file before starting any task.

## Project

Equilibrium is an explainable rare-disease atlas, launched as a long-running project (it began as
a Hack-Nation entry). The owner is @alijendoubi, who is the only approver and the only person who
merges.

- `backend/`: FastAPI + uv (`atlas.api.main:app`), graph snapshot in `data/`
- `frontend/`: Next.js 15 + pnpm 11, Tailwind 4, zod
- Flows: orb home → `/search` → `/disease/[id]` → `/map` (evidence map) → `/actions/[id]`

Every edge shown must be a sourced claim. Hypotheses are drawn dashed and contradictions in red.
Never fabricate evidence, citations or data.

## Lanes (who owns which paths)

| Lane            | Owns                                                                          | Typical work                                                                             |
| --------------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **Claude Code** | `frontend/**`, `docs/**`, `README.md`, `AGENTS.md`                            | UX and product copy, removing hackathon framing, issue triage, reviewing Codex PRs, docs |
| **Codex**       | `backend/**`, `data/**`, `scripts/**`, `.github/**`, `render.yaml`, Dockerfiles | API and data work, ingest and eval pipelines, deploy config, CI, backend hardening       |

If a task needs a change outside your lane, don't make it. Open an issue labelled with the other
lane (`agent:claude` / `agent:codex`) that describes the contract you need: endpoint, schema and
example payload. API contract changes go to the backend first; the frontend follows in a
separate PR.

## Task board

GitHub issues are the single source of truth.

- To claim a task, add `agent:claude` or `agent:codex` and comment `claimed`.
- One issue gives one branch and one PR. Never work on an issue claimed by the other lane.
- If the work isn't on the board yet, create the issue before you start.
- `blocked:owner` means the task needs the owner (secrets, billing, merges, product decisions).

## Workflow rules

- Work in your own git worktree on a branch named `<type>/<short-name>`. Never commit to `main` and
  never force-push.
- Use conventional commits: `feat|fix|refactor|docs|test|chore|perf|ci: ...`. The PR title must
  use the same format, because a CI check enforces it.
- Keep PRs small and focused. The PR body needs a summary, a test plan with checkboxes, and
  `Closes #N`.
- Never merge. The owner merges.
- Don't touch uncommitted work or branches you didn't create.
- No secrets in code, logs or PRs. Use env vars and keep `.env.example` files up to date.
- Validate inputs at system boundaries: zod in the frontend, pydantic in the backend.

## Definition of done

Run the checks locally. CI does not run while the GitHub account is billing-locked.

```bash
# backend (coverage must stay >= 80%)
cd backend && uv run pytest -q && uv run ruff check .

# frontend
cd frontend && pnpm typecheck && pnpm lint && pnpm format:check && pnpm test && pnpm build

# e2e, for user-facing changes (after pnpm build)
PORT=3010 pnpm start   # in another shell
E2E_BASE_URL=http://localhost:3010 pnpm test:e2e
```

Paste the actual pass counts into the PR test plan. Never write "should pass".

## Current priorities (launch)

Claude Code:

1. Triage open issues #25, #26, #27, #32, #35, #40: close the hackathon-only ones and relabel
   the ones that carry over.
2. Remove hackathon framing: the home page footer, README, metadata and milestone names.
3. Polish the frontend once the owner's evidence skyline view lands; check accessibility and
   responsive layout at 375/768/1440 in both themes.
4. Review every Codex PR before the owner merges it.

Codex:

1. #32 curated seed data (`data/curated/*.yaml`) with schema validation and tests.
2. #35 extraction quality: quote verification, the 30-abstract gold set and an eval script.
3. #25 deploy config (Render backend + Vercel frontend). Document env vars; the owner sets the
   secrets.
4. Backend hardening: per-IP rate limiting on `/api/v1/search` and `/api/v1/graph` (the home page
   calls both through a server action), plus a structured error envelope.

## Handoff

When a PR is ready, comment on its issue:
`ready for review: #PR, touched <paths>, needs <other lane> follow-up: yes/no`.
