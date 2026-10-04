# data/curated/

Hand-curated records that no public API provides in usable form: patient organizations and reusable assets (trials, registries, biomarkers, key publications). The pipeline turns them into `represents`, `operates` and `studies_condition` edges with `evidence_type: curated`. See [docs/EVIDENCE_MODEL.md](../../docs/EVIDENCE_MODEL.md).

Current slice: **Gaucher / GBA1 -> Parkinson's** ([ADR 0003](../../docs/adr/0003-demo-cluster-gaucher-gba1.md)).

## Rule

**Every entry needs a `url` and a `retrieved` date.** An entry without both is invalid and the loader must reject it. Do not add facts you did not see on the page at `url`. Never add patient-identifying data.

## Files

| File | Top-level keys |
|---|---|
| `organizations.yaml` | `organizations` (list), `no_dedicated_org_found` (diseases with no dedicated org; feeds the coverage report) |
| `assets.yaml` | `assets` (list) |
| `mechanisms.yaml` | `mechanisms` (list): GO biological-process whitelist (id, name, url, retrieved, curator, notes). Ids checked on QuickGO |
| `condition_aliases.yaml` | `aliases` (list): registry condition names -> slice MONDO id, used only when the MONDO label/synonyms do not match (name, disease_id, url, retrieved, curator, notes) |

## Entry fields

| Field | Required | Description |
|---|---|---|
| `id` | yes | Unique kebab-case slug |
| `name` | yes | Name as shown on the source |
| `type` | yes | Orgs: `patient_org`, `patient_org_umbrella`, `research_funder_program`, `research_charity`. Assets: `interventional_trial`, `observational_registry`, `natural_history_registry`, `biomarker`, `model_system`, `publication_clinical_evidence`, `publication_case_report` |
| `url` | yes | Page the facts were read from |
| `disease_ids` | yes | MONDO CURIEs from the seed list in [DATA_SOURCES.md](../../docs/DATA_SOURCES.md) |
| `retrieved` | yes | ISO date the URL was read |
| `curator` | yes | Who curated it. Agent-curated entries say `claude-agent, needs human check` |
| `notes` | yes | Short, factual; mark anything unverified `[U]` and anything inferred "hypothesis" |
| `verified` | orgs | What was actually checked (for example "url resolves" vs "page read") |
| `source_record_id` | assets | NCT id, `PMID:` id, or registry id |
| `attributes` | no | Registry fields (phase, status, enrollment, sponsor, dates) |
| `funds` / `operates` | no (orgs) | Asset slugs from `assets.yaml` the org funds or operates; becomes a `funds` / `operates` edge backed by the org's `url` |

## Graph ids (ingest/curated.py)

| Entry | Node id | Node type |
|---|---|---|
| organization | `org:<id>` | `patient_group` (`funder` for `research_funder_program`, `research_charity`) |
| asset with `source_record_id: NCT...` | `clinicaltrials:<NCT>` (merges with the ClinicalTrials.gov record) | `study` |
| `publication_*` asset with `source_record_id: PMID:...` | `PMID:<n>` | `publication` |
| any other asset | `asset:<id>` | `asset` |
| mechanism | the GO id | `mechanism` |

Validate with:

```bash
python -c "import yaml; [yaml.safe_load(open(f, encoding='utf-8')) for f in ('data/curated/organizations.yaml', 'data/curated/assets.yaml')]"
```
