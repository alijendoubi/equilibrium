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

## Demo cluster: Gaucher / GBA1 -> Parkinson's

**Decision (2026-10-03, task A1, issue #14):** the demo cluster is **Gaucher / GBA1 -> Parkinson's, plus lysosomal neighbours**. The hero is neuronopathic Gaucher disease (types 2 and 3) and the partner is GBA1-associated Parkinson's. The honest-gap disease is **saposin C deficiency**. Rationale and alternatives are in [ADR 0003](adr/0003-demo-cluster-gaucher-gba1.md). Snapshot slug: `gba1`.

The seed list below was checked live on 2026-10-03:
- **[V]** means verified today against the URL or API named.
- **[U]** means still to verify.
- Monarch means `https://api-v3.monarchinitiative.org/v3/api/entity/<ID>`. HGNC means `https://rest.genenames.org/fetch/symbol/<SYMBOL>`. CT.gov means `https://clinicaltrials.gov/api/v2/studies/<NCT>`.

### Diseases

| Disease | MONDO | ORPHA | OMIM | HPO terms (Monarch) | Gene link (Monarch, source) | Role |
|---|---|---|---|---|---|---|
| Gaucher disease (grouping) | MONDO:0018150 | 355 | n/a | 92 | n/a | Search entry point |
| Gaucher disease type I | MONDO:0009265 | 77259 | 230800 | 59 | GBA1 `causes` (OMIM) | Context: has approved ERT/SRT, so it is not the hero |
| **Gaucher disease type II** | MONDO:0009266 | 77260 | 230900 | 51 | GBA1 `causes` (OMIM) | **Hero (nGD, acute)** |
| **Gaucher disease type III** | MONDO:0009267 | 77261 | 231000 | 50 | GBA1 `causes` (OMIM) | **Hero (nGD, chronic)** |
| Gaucher disease perinatal lethal | MONDO:0011945 | 85212 | 608013 | 64 | GBA1 `causes` (OMIM) | Severe end of the spectrum |
| Gaucher disease-ophthalmoplegia-cardiovascular calcification syndrome | MONDO:0009268 | 2072 | 231005 | 64 | GBA1 `causes` (OMIM) | Optional |
| **Late-onset Parkinson disease** (GBA1-PD susceptibility) | MONDO:0008199 | 411602 | 168600 | 47 | GBA1 `contributes_to` (OMIM); `gene_associated_with_condition` (Orphanet) | **Partner disease** |
| Lewy body dementia | MONDO:0007488 | 1648 | 127750 | not checked | GBA1 `contributes_to` (OMIM) | Optional second common-disease bridge |
| **Gaucher disease due to saposin C deficiency** | MONDO:0012517 | 309252 | 610539 | 36 | PSAP `causes` (OMIM) | **Honest gap** |
| Combined PSAP deficiency | MONDO:0012719 | 139406 | 611721 | 20 | PSAP `causes` (OMIM) | Neighbour |
| Parkinson disease 24, AD, susceptibility to | MONDO:0859183 | n/a | 619491 | 4 | PSAP `contributes_to` (OMIM) | Hypothesis hop. The link is contested; see contradictions |
| Action myoclonus-renal failure syndrome | MONDO:0009699 | 163696 | 254900 | 23 | SCARB2 `causes` (OMIM) | Neighbour (GCase trafficking) |
| Niemann-Pick disease type A | MONDO:0009756 | 77292 | 257200 | 37 | SMPD1 `causes` (OMIM) | Neighbour |
| Niemann-Pick disease type B | MONDO:0011871 | 77293 | 607616 | 60 | SMPD1 `causes` (OMIM) | Neighbour |
| Kufor-Rakeb syndrome (PARK9) | MONDO:0011706 | 306674 | 606693 | 67 | ATP13A2 `causes` (OMIM) | Neighbour: lysosomal and parkinsonism |
| Neuronal ceroid lipofuscinosis 10 | MONDO:0012414 | 228337 | 610127 | 27 | CTSD `causes` (OMIM) | Neighbour |
| Hereditary spastic paraplegia 46 | MONDO:0013737 | 320391 | 614409 | 50 | GBA2 `causes` (OMIM) | Neighbour (same substrate, non-lysosomal enzyme) |

All rows are [V] via Monarch entity and association endpoints. Notes:
- Monarch also lists SCARB2 as `gene_associated_with_condition` with Gaucher disease type I (Orphanet). This supports the SCARB2-GCase hop.
- Monarch has **no** curated gene-disease edge for SMPD1 and PD, or for ATP13A2 and CLN12. Those links come from the literature and must be shown as hypotheses.

### Genes

| Symbol | HGNC ID | Name | Previous symbols | OMIM gene |
|---|---|---|---|---|
| GBA1 | HGNC:4177 | glucosylceramidase beta 1 | GBA, GLUC | 606463 |
| PSAP | HGNC:9498 | prosaposin | SAP1, GLBA, SAP2 | 176801 |
| SCARB2 | HGNC:1665 | scavenger receptor class B member 2 (LIMP-2) | CD36L2 | 602257 |
| SMPD1 | HGNC:11120 | sphingomyelin phosphodiesterase 1 | none | 607608 |
| GBA2 | HGNC:18986 | glucosylceramidase beta 2 | SPG46 | 609471 |
| ATP13A2 | HGNC:30213 | ATPase cation transporting 13A2 | PARK9 | 610513 |
| CTSD | HGNC:2529 | cathepsin D | CPSD | 116840 |
| LRRK2 | HGNC:18618 | leucine rich repeat kinase 2 (optional; lysosome links are literature-only [U]) | PARK8 | 609007 |
| SNCA | HGNC:11138 | synuclein alpha (optional PD context) | PARK1, PARK4 | 163890 |

All rows are [V] via the HGNC REST API. Search must resolve the old symbol "GBA" to GBA1.

### Key HPO phenotypes for neuronopathic Gaucher disease

[V] Monarch DiseaseToPhenotypicFeature associations for MONDO:0009266 and MONDO:0009267:
- HP:0000605 Supranuclear gaze palsy (type II); HP:0007817 Horizontal supranuclear gaze palsy (type III); HP:0007885 Slowed horizontal saccades (III, frequent)
- HP:0000657 Oculomotor apraxia (II); HP:0000602 Ophthalmoplegia (II, III)
- HP:0001250 Seizure; HP:0002123 Generalized myoclonic seizure; HP:0001336 Myoclonus (III)
- HP:0001251 Ataxia (III); HP:0001263 Global developmental delay (II); HP:0007272 Progressive psychomotor deterioration (II)
- HP:0002179 Opisthotonus; HP:0010307 Stridor; HP:0002015 Dysphagia; HP:0001257 Spasticity (II)
- HP:0001744 Splenomegaly; HP:0002240 Hepatomegaly; HP:0001873 Thrombocytopenia (II, III)
- HP:0003656 Decreased beta-glucocerebrosidase level (II, III)

### Trials and studies

| NCT | Short name | Population | Intervention | Phase | Status (CT.gov, 2026-10-03) | Role |
|---|---|---|---|---|---|---|
| NCT05778617 | ASPro-PD | PD within 7 years of diagnosis, age 35-75, GBA1-positive or negative (about 165 carriers per Cure Parkinson's) | Ambroxol, titrated to 1260 mg/day, vs placebo, 104 weeks; primary MDS-UPDRS I-III | 3 | Recruiting; est. 330; primary completion 2029-02 | **Reusable asset (PD side)** |
| NCT04388969 | Ambroxol IIR registry | Gaucher disease or GBA carriers with PD | Ambroxol real-world data (observational) | n/a | Recruiting; est. 300; to 2030-11 | **Asset already spanning both communities** |
| NCT04127578 | PROPEL | PD with at least one GBA1 variant | LY3884961 (PR001) gene therapy | 1/2 | Active, not recruiting; est. 32 | Same product as PROVIDE |
| NCT04411654 | PROVIDE | Infants with Gaucher type 2 | LY3884961 (PR001) gene therapy | 1/2 | Active, not recruiting; 7 enrolled | Hero-side trial |
| NCT05222906 | LEAP2MONO | Gaucher type 3, age 12+, stable on ERT | Venglustat vs imiglucerase | 3 | Active, not recruiting; 43 | Counterexample pair (positive in GD3) |
| NCT02906020 | MOVES-PD | GBA-PD | Venglustat vs placebo | 2 | Terminated: "did not meet the primary or secondary endpoints"; has results | Counterexample pair (negative in PD) |
| NCT05819359 | ACTIVATE | GBA-PD | BIA 28-6156 (GCase activator) | 2 | Active, not recruiting; est. 237 | PD-side asset |
| NCT00358943 | ICGG Gaucher Registry | All Gaucher disease | Observational registry (Sanofi/Genzyme), since 1991 | n/a | Recruiting; est. 12,000 | Natural history asset |
| NCT03291223 | Gaucher Outcome Survey (GOS) | All Gaucher disease | Observational registry (Shire/Takeda) | n/a | Recruiting; est. 1,257 | Natural history asset |

All rows are [V] via CT.gov API v2. Outcome sources:
- MOVES-PD: Giladi et al., Lancet Neurol 2023, PMID 37479372 [V]. The MDS-UPDRS II+III difference was 2.58 points, worse on venglustat, not significant.
- LEAP2MONO: Sanofi press release, 2026-02-02 [V], https://www.sanofi.com/en/media-room/press-releases/2026/2026-02-02-06-00-00-3229947. Secondary reports quote different p-values, so cite the release only.

Key literature:
- **Narita et al. 2016**, Ann Clin Transl Neurol, PMID 27042680, PMC4774255, doi 10.1002/acn3.292 [V].
  - Design: open-label pilot in 5 nGD patients on ERT. Target dose 25 mg/kg/day (maximum 1300 mg/day).
  - Findings: crossed the blood-brain barrier, raised lymphocyte GCase, lowered CSF glucosylsphingosine.
- **Sidransky et al. 2009**, NEJM, PMID 19846850, PMC2856322 [V].
  - N370S or L444P found in 15% of Ashkenazi Jewish PD patients vs 3% of non-Ashkenazi patients. Full sequencing found 7% in non-Ashkenazi patients.
  - **Use this citation for the 15% / 3% figures, not PMC4351661.** PMC4351661 (Gan-Or et al. 2015) reports severe vs mild variant odds ratios, and "approximately 20%" founder variants in Ashkenazi patients.
- Reczek et al. 2007, Cell, PMID 18022370 [V]: LIMP-2 (SCARB2) is the receptor that targets GCase to the lysosome.
- Alcalay et al. 2019, Mov Disord, PMID 30788890 [V]: SMPD1 variants and PD.
- Oji et al. 2020, Brain, PMID 32201884 [V]: PSAP saposin D variants and PD. **Contested:** Brain 2021 commentaries, e.g. PMID 33793763 (Chinese cohort), with author replies.
- Saposin C deficiency treated with eliglustat for 9 years in one patient, Mol Genet Metab 2026, PMID 41812503 [V]. Systemic improvement, no seizure improvement.

### Patient organizations

Curated in [`data/curated/organizations.yaml`](../data/curated/organizations.yaml).

| Organization | URL | Check |
|---|---|---|
| National Gaucher Foundation (US) | https://www.gaucherdisease.org | [V] resolves (200); scope not read [U] |
| International Gaucher Alliance | https://www.gaucheralliance.org | [V] page read; UK charity 1192011 |
| The Gauchers Association (UK) | https://www.gaucher.org.uk | [V] page read; charity 1095657; has a "Parkinsons and Gaucher disease" page |
| Michael J. Fox Foundation: GBA1-PD Research Catalyst Program | https://www.michaeljfox.org/grant/gba1-parkinsons-disease-research-catalyst-program | [V] resolves; programme described via search |
| Cure Parkinson's (ASPro-PD co-funder) | https://cureparkinsons.org.uk/research/research-projects/ambroxol/ | [V] page read |
| Parkinson's UK (GBA1-PD Catalyst partner) | https://www.parkinsons.org.uk | [V] resolves |

**Warning:** `gaucherregistry.com` is **not** the ICGG registry. On 2026-10-03 it served an online casino. Link the ICGG registry through CT.gov (NCT00358943) or https://www.icgg.org (resolves; content not read [U]).

### Honest gap: Gaucher disease due to saposin C deficiency (MONDO:0012517)

Searches run on 2026-10-03:

| Source | Query | Result |
|---|---|---|
| ClinicalTrials.gov v2 | `query.cond="saposin C deficiency"` | **0** |
| ClinicalTrials.gov v2 | `query.term="saposin C deficiency"` | 1 (NCT04221451, a GM2 venglustat trial; not about this disease) |
| NIH RePORTER v2 | `"saposin C deficiency"` in title/terms/abstract | **0** projects |
| PubMed | `"saposin C deficiency"` | 20 records |
| Patient orgs | Web search + NORD + Global Genes | No dedicated org. NORD and Global Genes have disease pages only; general Gaucher orgs cover it [V]. Orphanet directory not checked [U] |
| Therapy | PMID 41812503 | "To date, no specific therapy is approved for Sap C deficiency"; ERT "biologically implausible" |

Why this disease:
- It sits one hop from the hero. Same substrate (glucosylceramide), and the same enzyme lacks its activator.
- It has a real but weak lead: SRT (eliglustat) in a single case, and a brain-penetrant SRT (venglustat) in GD3. That gives a concrete next question.

Runner-up: action myoclonus-renal failure (SCARB2). It had 0 CT.gov records and 0 RePORTER projects for the exact phrase, but it is further from the hero mechanism.

### Contradictions and counterexamples to seed

1. **Venglustat:** negative in GBA-PD (MOVES-PD) and positive in GD3 (LEAP2MONO).
2. **PSAP and PD susceptibility:** OMIM/Monarch edge, contested by replication letters.
3. **Ambroxol:** the nGD pilot dosing is weight-based (25 mg/kg/day, max 1300 mg/day, with ERT). ASPro-PD uses a fixed 1260 mg/day in adults. Show this as "what differs", never as dosing guidance.

### Open [U] items

- Exact scope pages of the National Gaucher Foundation and https://www.icgg.org
- Orphanet patient-org directory entries for saposin C deficiency
- Literature basis for LRRK2-lysosome links
- ATP13A2 as CLN12 (not in Monarch)
- FDA venglustat target action date 2026-11-25: from press coverage of Sanofi's May 2026 release, not read on fda.gov

## Attribution

When the dataset is published, the snapshot `manifest.json` and the UI footer must cite each source and its version, as its license requires. See [data/README.md](../data/README.md).
