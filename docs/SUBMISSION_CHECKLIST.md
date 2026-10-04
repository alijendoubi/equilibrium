# Submission Checklist

Work top to bottom. Owner: **Ali (@alijendoubi)**. Deadline: **2026-10-04, about 12:30 local time**. Ticked items were verified on 2026-10-04.

## 1. Merge and data

- [ ] Merge the single combined PR (the tip of the stack). Do not merge the stacked PRs one by one: squash merges would conflict.
- [x] `make data-offline` rebuilds a byte-identical snapshot from the committed cache (enforced by a test)
- [x] Curated data: all 18 source URLs return 200; all 9 trials match live ClinicalTrials.gov (status, phase, enrolment, conditions). See #32.
- [ ] Clara: human read of the organisation notes in `data/curated/organizations.yaml` (#32)

## 2. OpenAI (required for the prize track)

Run from `backend/` with `OPENAI_API_KEY` set, then commit `data/cache` and `data/snapshot`:

- [ ] `make openai-smoke`: gpt-6.1-sol and gpt-6-luna structured outputs, plus embeddings. If Luna fails, set `OPENAI_MODEL_RECONCILE=gpt-5.4-mini`.
- [ ] `uv run python -m atlas.extract.cli run`: about 147 abstracts, a few USD
- [ ] `uv run python -m atlas.pipeline build --offline`: snapshot with extracted claims and real `openai_usage`
- [ ] `uv run python -m atlas.reconcile.cli embed --nodes ../data/snapshot/atlas-snapshot.json`
- [ ] `uv run python -m atlas.explain.cli golden`: AI briefs for the demo path
- [ ] Spend limit set on the OpenAI project (recommended $50)

## 3. Deploy

- [ ] Render: New + then Blueprint (`render.yaml`). Set `OPENAI_API_KEY`, and set `CORS_ORIGINS` to the Vercel URL. Keep `EXPLAIN_LIVE=0`: the image ships the committed caches.
- [ ] `https://<render>/health` returns `"snapshot":"loaded"`, and `/api/v1/meta` shows the snapshot id and OpenAI usage
- [ ] Vercel: import the repo with Root Directory `frontend`. Set `NEXT_PUBLIC_USE_MOCKS=false` and `NEXT_PUBLIC_API_URL=https://<render>`, then redeploy after setting them.
- [ ] On the Vercel URL, the journey works with **no** "Showing cached demo data" notice: Gaucher type II, the path to ASPro-PD, the evidence panel, the action view ("what differs" shows doses), the brief labelled **AI-generated**, and the saposin C deficiency gap card. Click "Draft collaboration brief" once in the browser to prove CORS works.
- [ ] Render is on a non-sleeping plan (starter) during judging
- [x] Local run verified: backend on the real snapshot plus frontend in live mode, all demo pages 200 with no fallback, explain passes CORS (2026-10-04)

## 4. Repository and README

- [x] Built with OpenAI section (three jobs, models, guarantees, precompute commands)
- [x] Deploy section and `render.yaml`
- [x] Reproducing the dataset section with real commands
- [x] Team table (Ali, Khaled, Clara)
- [x] LICENSE (MIT); data attribution in docs/DATA_SOURCES.md
- [ ] README Status section: date it and mark what is done or planned (honestly)
- [ ] Add the live URLs and video links at the top of the README
- [ ] Search for leftover placeholders: `TODO`, `TBD`, `[TEAM DECISION`

## 5. Videos (Clara narrates, Ali drives)

- [ ] 1-minute walkthrough recorded from [DEMO_SCRIPT.md](DEMO_SCRIPT.md) on the deployed URL: `[LINK]`
- [ ] Team video, 2-3 minutes: `[LINK]`
- [ ] Both links viewable in a private window; added to the README and the submission form
- [ ] `gaucherregistry.com` is not used anywhere (it serves an online casino)

## 6. Security and release

- [x] Repository public, ruleset active, private vulnerability reporting on
- [x] No secrets in the repo or caches (security review, 2026-10-04)
- [x] Public `/explain` cannot run up OpenAI cost: live calls are off by default and rate limited per IP
- [ ] Tag the release (GitHub Actions do not run on this account, so create it by hand): `git tag -a v1.0.0 -m "Hack-Nation submission" && git push origin v1.0.0 && gh release create v1.0.0 --generate-notes`
- [ ] Submit the form and keep the confirmation
- [ ] After judging: rotate the OpenAI, Vercel and Render keys
