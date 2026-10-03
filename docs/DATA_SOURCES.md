# Data Sources

This file lists every source named in the challenge brief, plus a few supporting ones. **None are ingested yet** (Phase 2).

"Verify" means nobody on the team has yet read the current license or terms page. The person who adds the connector must check it and replace "verify" with the actual terms and a link.

## Priority legend

- **P0:** needed for the 24-hour slice and Maria's journey
- **P1:** strengthens the demo if time allows
- **P2:** stretch or post-hackathon

## Sources

### Biology engine

| Source | URL | Access | License / terms | Feeds | Priority |
|---|---|---|---|---|---|
| MONDO | https://mondo.monarchinitiative.org | OBO / JSON release download (GitHub releases) | CC BY 4.0 (verify) | disease nodes, synonyms, xrefs (ORPHA, OMIM, DOID) | P0 |
| HPO | https://hpo.jax.org | `hp.obo` / `phenotype.hpoa` download | HPO license, free use with attribution and version citation (verify) | `has_phenotype`, phenotype IC | P0 |
| ClinVar | https://www.ncbi.nlm.nih.gov/clinvar/ | FTP (`variant_summary.txt.gz`) or E-utilities | Public domain, NCBI usage policies (verify) | `has_variant`, `variant_associated_with`, review status for confidence | P0 |
| OMIM | https://omim.org | REST API with an API key (`OMIM_API_KEY`) | Requires registration; license restricts redistribution (verify before any snapshot) | `caused_by`, mechanism text | P1 |
| HGNC | https://www.genenames.org | REST / download | Free to use (verify) | gene IDs and symbols for Reconcile | P0 (support) |

### Research signal

| Source | URL | Access | License / terms | Feeds | Priority |
|---|---|---|---|---|---|
| PubMed | https://pubmed.ncbi.nlm.nih.gov | NCBI E-utilities (`NCBI_API_KEY` raises the rate limit) | Metadata is free. Abstracts may be under publisher copyright: store IDs, short quotes and extracted facts only (verify) | publications, `claims`, `authored_by` | P0 |
| PMC Open Access | https://www.ncbi.nlm.nih.gov/pmc/ | OA subset / BioC API | Per-article license (CC BY, CC BY-NC and others) (verify) | full-text claims | P2 |
| NIH RePORTER | https://reporter.nih.gov | RePORTER API v2 (no key) | Public data (verify) | `funds`, `works_on`, investigators, active programs | P1 |

### Assets already built

| Source | URL | Access | License / terms | Feeds | Priority |
|---|---|---|---|---|---|
| ClinicalTrials.gov | https://clinicaltrials.gov | API v2 (JSON) | Public, NLM terms (verify) | `studies_condition`, `tests_intervention`, natural history studies | P0 |
| Patient-org websites and press releases | various | Manual curation; respect robots.txt and site terms | Per site (verify) | `operates` (registries, biobanks), assets | P1 |

### Patient-group directories

| Source | URL | Access | License / terms | Feeds | Priority |
|---|---|---|---|---|---|
| Orphanet / Orphadata | https://www.orpha.net, https://www.orphadata.com | Orphadata XML/JSON products | CC BY 4.0 (verify) | disease xrefs, gene-disease, expert and patient orgs | P0 |
| NORD | https://rarediseases.org | Website (organization directory) | Site terms; no bulk API known (verify) | `represents` | P1 (manual) |
| Global Genes | https://globalgenes.org | Website (foundation directory) | Site terms (verify) | `represents` | P1 (manual) |
| EURORDIS | https://www.eurordis.org | Website (member directory) | Site terms (verify) | `represents` | P2 |
| Rare Disease UK | https://www.raredisease.org.uk | Website | Site terms (verify) | `represents` | P2 |
| Genetic Alliance | https://geneticalliance.org | Website | Site terms (verify) | `represents` | P2 |

### Stretch sources

| Source | URL | Access | License / terms | Feeds | Priority |
|---|---|---|---|---|---|
| The Jackson Laboratory (mouse models) | https://www.jax.org, https://www.informatics.jax.org | MGI downloads / JAX strain search | MGI data is free with citation; strain catalog per site terms (verify) | `asset` (models) | P2 |
| RareConnect | https://www.rareconnect.org | Website | Site terms (verify) | patient communities | P2 |
| bioRxiv / medRxiv | https://www.biorxiv.org, https://www.medrxiv.org | bioRxiv API | Per-preprint license (verify) | newest `claims` (low base confidence) | P2 |

## Recommended 24-hour slice

The brief says: *"Begin with a focused slice that has enough biology, research, and patient-group information to demonstrate a complete path."* Pick **one cluster** of roughly 5 to 15 diseases where:

1. Several **different genes converge on a shared mechanism**. This is the brief's "names hide mechanisms" point.
2. **HPO annotations are rich**, so phenotype similarity means something.
3. At least one **patient registry or natural history study** exists in ClinicalTrials.gov or on organization sites, so there is a reusable asset to find.
4. At least one disease is **sparse**, with no organization or study, so we can demo the honest-gap path.

**Candidates (team decision, not yet made):**

| Candidate cluster | Why it fits | Risk |
|---|---|---|
| Lysosomal storage disorders, for example a subset of the mucopolysaccharidoses or neuronal ceroid lipofuscinoses | The brief cites lysosomal storage directly. Many genes share a clearance mechanism. There are many registries and natural history studies, and existing enzyme-replacement assets. | Some members have approved therapies. The demo should focus on members that do not. |
| Developmental and epileptic encephalopathies / channelopathies (for example SCN-family, KCNQ2, STXBP1-related) | Same-gene, different-mechanism cases (loss vs gain of function). Strong HPO coverage. Active patient groups. The brief's UI mock uses STXBP1. | Mechanism labels need careful sourcing. |
| Congenital disorders of glycosylation | Many genes, shared pathway, many untreated members, active community | Smaller literature per disease |

**Decision:** `[TEAM DECISION - TODO: cluster name, list of MONDO IDs, owner, date]`. Record the decision here and in the M2 milestone.

## Attribution

When the dataset is published, the snapshot `manifest.json` and the UI footer must cite each source and its version, as its license requires. See [data/README.md](../data/README.md).
