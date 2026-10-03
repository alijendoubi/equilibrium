# Runbook

These are operational steps for setting up and running the repo, CI and deploys. Commands assume:
- the `gh` CLI is authenticated as a repo admin
- the shell is at the repo root

## 1. Bootstrap the GitHub repository

```bash
bash scripts/github/bootstrap-repo.sh
```

The script applies the following. Read the script for the exact behavior.
- the `main-protection` ruleset from `.github/rulesets/main.json`:
  - PR required, code-owner approval (@alijendoubi only), stale approvals dismissed, approval must come after the last push
  - review threads must be resolved
  - squash-only merges, linear history, no force push
  - required checks `backend`, `frontend`, `pr-title` and `secrets-scan`
  - admin bypass
- labels: `type:*`, `area:*`, `priority:P0-P2`, `module:*`, `size/*` and `run-e2e`
- milestones M1 to M5

**Note:** the repository is **public**, so the ruleset is enforced on the free plan. (Rulesets on a private repository are enforced only on a paid plan; `apply_ruleset` warns and continues in that case, and retries transient HTTP 403s that GitHub can return right after a visibility change.) `scripts/github/go-public.sh` is kept for re-running the flip on a fork or a fresh copy.

Verify:

```bash
gh api repos/alijendoubi/equilibrium/rulesets --jq '.[] | {name, enforcement}'
gh label list --limit 100
gh api repos/alijendoubi/equilibrium/milestones --jq '.[].title'
```

## 2. Invite collaborators

```bash
gh api -X PUT repos/alijendoubi/equilibrium/collaborators/<user> -f permission=push
```

Repeat for each teammate. Each person must accept the invitation from their email or from https://github.com/notifications. List pending invitations:

```bash
gh api repos/alijendoubi/equilibrium/invitations --jq '.[].invitee.login'
```

## 3. Set Actions secrets

```bash
gh secret set OPENAI_API_KEY            # paste when prompted (stays out of shell history)
gh secret set VERCEL_TOKEN
gh secret set VERCEL_ORG_ID
gh secret set VERCEL_PROJECT_ID
gh secret set RENDER_DEPLOY_HOOK_URL
gh secret list
```

Deploy jobs **skip** when their secrets are missing, so CI stays green before deploy targets exist.

## 4. Connect Vercel (frontend)

1. In Vercel, add a new project and import `alijendoubi/equilibrium`.
2. Leave **Root Directory** empty. `deploy.yml` already runs the Vercel CLI from `frontend/`, so setting it to `frontend` would make Vercel look for `frontend/frontend`. The framework preset (Next.js) and the pnpm install command are detected automatically.
3. Add environment variables for both Production and Preview:
   - `NEXT_PUBLIC_API_URL`: the Render backend URL, for example `https://<service>.onrender.com`
   - `BACKEND_URL`: the same URL
4. Get the IDs:
   - run `pnpm dlx vercel link` inside `frontend/`, then read `.vercel/project.json` for `orgId` and `projectId`
   - or copy them from Project Settings
5. Create a token at https://vercel.com/account/tokens.
6. Set the `VERCEL_*` secrets from step 3.
7. If `deploy.yml` deploys through the CLI, consider disabling Vercel's own Git auto-deploy to avoid duplicate deploys. Check `deploy.yml` first.

## 5. Connect Render (backend)

1. In Render, create a new **Web Service** from `alijendoubi/equilibrium`.
2. Set the runtime to **Docker**, the **Root Directory** to `backend`, and the Dockerfile path to `./Dockerfile` (Render resolves it relative to the Root Directory).
3. Set the **Health Check Path** to `/health`.
4. Add environment variables:
   - `OPENAI_API_KEY`
   - optionally `OPENAI_MODEL_EXTRACT`, `OPENAI_MODEL_EXPLAIN`, `OPENAI_MODEL_RECONCILE`, `OPENAI_EMBED_MODEL` (defaults: `gpt-6.1-sol`, `gpt-6.1-sol`, `gpt-6-luna`, `text-embedding-3-small`)
   - `CORS_ORIGINS`: the Vercel production URL and the preview pattern
   - `LOG_LEVEL=INFO`
   - optionally `NCBI_API_KEY` and `OMIM_API_KEY`
5. Turn auto-deploy off if deploys should come only from `deploy.yml` on `main`.
6. Under Settings, then **Deploy Hook**, copy the URL and run `gh secret set RENDER_DEPLOY_HOOK_URL`.
7. Free instances sleep when idle. Warm the service before judging, or upgrade it.

## 6. Local development

```bash
cp .env.example .env
make setup
make dev-backend      # :8000
make dev-frontend     # :3000
# or
docker compose up --build
make check            # same gates as CI
```

## 7. Troubleshooting CI

| Symptom | Likely cause | Fix |
|---|---|---|
| `pr-title` fails | Title is not a Conventional Commit | Edit the title, for example `feat(ui): add edge panel`. The check re-runs. |
| `secrets-scan` fails | gitleaks found a secret-like string | If it is real: **rotate the key** (see SECURITY.md) and remove it. If it is a false positive: add a narrow allowlist entry to `.gitleaks.toml` in a `chore/` PR. |
| `backend` fails on lint or format | ruff | `make fmt`, then `make lint` |
| `backend` fails on coverage | Coverage below 80% | Add tests. Do not lower the threshold. |
| `backend` fails on typecheck | mypy errors | Run `make typecheck` locally and fix the types |
| `frontend` fails on install | Lockfile out of date | `cd frontend && pnpm install` and commit `pnpm-lock.yaml` |
| `frontend` fails on build | Type errors or a missing env | `make build`. Env vars needed at build time must have safe defaults. |
| Required check shows "Expected - waiting" forever | The job name differs from the required check name, or the workflow was path-filtered out | Make sure the job names are exactly `backend` and `frontend`. Path-filtered workflows still need to report a status. |
| Deploy job skipped | Secrets are missing | Expected until step 3 is done |
| Vercel preview 404s on API calls | `NEXT_PUBLIC_API_URL` is not set for Preview | Set it in Vercel and redeploy |
| Browser shows CORS errors | `CORS_ORIGINS` is missing the frontend origin | Update it on Render and redeploy |
| E2E did not run | Label is missing | Add the `run-e2e` label to the PR |
| Cannot merge with checks green | Unresolved threads, stale approval, or branch is behind | Resolve the threads, re-request review, update the branch |
