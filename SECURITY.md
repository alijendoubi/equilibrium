# Security Policy

## Supported versions

This is a hackathon prototype. Only the latest commit on `main` and the deployed demo are supported.

## Reporting a vulnerability

**Do not open a public issue for a vulnerability.**

- Report it privately through GitHub private vulnerability reporting: [open a draft security advisory](https://github.com/alijendoubi/equilibrium/security/advisories/new) (or **Security** tab, then **Report a vulnerability**).
- This is the only reporting channel. The report is visible only to you and the maintainer (@alijendoubi).

Include the affected component, steps to reproduce and the impact. During the event we aim to acknowledge reports within 24 hours.

## Secrets

- **No secrets in the repository.** Configuration is read from environment variables. `.env` is gitignored, and only `.env.example`, which contains placeholders, is committed.
- **gitleaks is enforced:** the pre-commit hook scans locally, and the required `secrets-scan` check in `security.yml` scans every PR. A PR with a detected secret cannot merge.
- CI and deploy credentials live in GitHub Actions secrets: `OPENAI_API_KEY`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` and `RENDER_DEPLOY_HOOK_URL`. Runtime keys live in the Vercel and Render dashboards.
- Never print keys in logs, error messages or API responses.

### If a key leaks

1. **Revoke the key first** at the provider: OpenAI dashboard, Vercel tokens, NCBI account, OMIM, or regenerate the Render deploy hook.
2. Issue a new key and update it everywhere it is used:
   - `gh secret set <NAME>`
   - Vercel and Render environment settings
   - your local `.env`
3. Remove the secret from the code in a PR. Rewriting history does **not** make a pushed secret safe. Rotation is what matters.
4. Check provider usage logs for abuse, especially OpenAI spend.
5. Tell the team in the team channel and record the incident in the PR.

The repository is now public: rotate every key used during the hackathon at submission. See [docs/SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md).

## Data handling

- **Public datasets only.** The atlas is built from public biomedical databases and from public patient-organization information.
- **No patient PII or PHI.** We never ingest, store or log personal health data about individuals. This includes names of individual patients, case reports that identify a person, and free-text user input saved to disk. Patient organizations are included as organizations only.
- **Named investigators** are public professional information taken from publications and grant records. We store only names, affiliations and source links.
- **Respect source licenses and terms.** Every license below must be verified by the person adding the source. See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
  - **OMIM** requires an API key and is subject to OMIM license terms. Redistribution is restricted. Do not commit OMIM data to the repo or to published snapshots unless the terms allow it.
  - **ClinVar** (NCBI) and **HPO** and **MONDO** are openly available. HPO and MONDO require attribution. Verify the current license text.
  - **PubMed / PMC:** store PMIDs, metadata and extracted facts. Do not redistribute full text unless the article license allows it.
  - **Patient organization sites:** follow each site's terms and robots.txt. Prefer manual curation over scraping.
- LLM calls send only public source text to the OpenAI API. Do not send user-entered personal information.

## Repository protections

The `main-protection` ruleset requires:
- a PR approved by the code owner (@alijendoubi), with the approval given after the last push (stale approvals are dismissed)
- all review threads resolved
- passing required checks
- linear, squash-only history with no force pushes

The repository is public and the ruleset is enforced (`enforcement: active`). See [docs/RUNBOOK.md](docs/RUNBOOK.md).
