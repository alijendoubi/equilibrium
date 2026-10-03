# Submission Checklist

Work through this list top to bottom before submitting. Owner: `[NAME - TODO]`. Deadline: `[DATE/TIME + TZ - TODO]`.

## Prototype

- [ ] Production frontend URL is live: `[URL - TODO]`
- [ ] Backend `GET /health` returns 200 on the production URL: `[URL - TODO]`
- [ ] `GET /api/v1/meta` shows the expected snapshot id and source list
- [ ] The full journey works on production: search, then mechanism, related disease, patient group, asset and next step
- [ ] The honest-gap path works for at least one sparse disease
- [ ] Every edge shown has a source link that opens. Spot-check 10.
- [ ] Backend instance is warm, or on a non-sleeping plan, during the judging window
- [ ] OpenAI spend limit is set on the account, so the demo cannot exhaust it or run up cost
- [ ] Local run verified from a clean clone: `cp .env.example .env && make setup && make dev-backend` / `make dev-frontend`, and `docker compose up --build`

## Repository and README

- [ ] README architecture section matches what was actually built (diagram and component status)
- [ ] README "Reproducing the dataset" works: `make data` from a clean clone produces the snapshot. Remove "Phase 2 / planned" labels only for parts that really work.
- [ ] `docs/DATA_SOURCES.md` has no remaining "verify" entries for sources that were actually used
- [ ] README Status section is updated with the date and the honest state of each milestone
- [ ] Team table is filled in with names, roles and GitHub handles
- [ ] All placeholders removed or filled: search the repo for `TODO`, `TBD` and `[TEAM DECISION` (the `CONTACT EMAIL` placeholders are resolved)
- [ ] Planned features are still labelled as planned. Nothing claims to exist when it does not.
- [ ] LICENSE present (MIT). Third-party data attribution present.

## Videos

- [ ] Team video uploaded: `[LINK - TODO]`
- [ ] 1-minute walkthrough uploaded: `[LINK - TODO]` (see [DEMO_SCRIPT.md](DEMO_SCRIPT.md))
- [ ] Both links are viewable by the public or by judges. Test them in a private window.
- [ ] Links added to the README and to the submission form

## Security and visibility

- [ ] Rotate all keys used during the hackathon: OpenAI, Vercel token, Render deploy hook, NCBI and OMIM. Update GitHub secrets and the deploy dashboards. See [SECURITY.md](../SECURITY.md).
- [ ] `secrets-scan` is green on `main`. Optionally run a full-history gitleaks scan: `gitleaks detect --source . --log-opts="--all"`
- [ ] No restricted data (for example OMIM) is committed or included in the published snapshot
- [x] Run `scripts/github/go-public.sh` to flip the repository to public (the repository is public)
- [x] Verify the ruleset is now enforced: `gh api repos/alijendoubi/equilibrium/rulesets` reports `enforcement: active`. A direct push to `main` is rejected for non-admins; the repository admin role has bypass, so do not test it with an admin account.
- [x] Enable private vulnerability reporting (Settings, then Security). Done 2026-10-03; SECURITY.md and CODE_OF_CONDUCT.md point to it and to @alijendoubi, with no contact email.

## Release

- [ ] All M5 issues are closed or moved
- [ ] Tag the release: `git tag -a v1.0.0 -m "Hack-Nation submission" && git push origin v1.0.0`. The `release.yml` workflow runs.
- [ ] GitHub release notes link the prototype, the videos and the snapshot
- [ ] Submission form completed and confirmation received
