# Equilibrium: Full Project Plan (Challenge 05, AI Atlas for the World's Rare Diseases)

Team Equilibrium (Ali, Sagor, Clara). Hack-Nation 7th Global AI Hackathon, OpenAI x Buffalo Initiative track.
Prepared 2026-10-03. Repo state: M1 bootstrap done. FastAPI `/health` + `/api/v1/meta`, draft `models/evidence.py`, Next.js landing shell, issues #14-#27 seeded, CI not executing (Actions blocked on account).

Legend: **[V]** = verified live during planning (API call, file HEAD, or official page read on 2026-10-03). **[U]** = unverified; whoever touches it confirms before relying on it.

---

## 1. Executive summary

**What we build.** An evidence-first atlas for one disease cluster: **GBA1/GCase–lysosomal dysfunction** (Gaucher / GBA1 -> Parkinson's, plus lysosomal neighbours). Parkinson's is the validated anchor; the value is in the less obvious neighbours, assets and gaps around it. The neighbour genes are PSAP, SCARB2, SMPD1, ATP13A2, CTSD and GBA2. The decision is in [ADR 0003](adr/0003-demo-cluster-gaucher-gba1.md), and the verified seed list is in [DATA_SOURCES.md](DATA_SOURCES.md#demo-cluster-gaucher--gba1---parkinsons).

Maria types her disease into one search box. The atlas walks her through a chain where every step cites an edge and every edge has a source link:
1. her disease (neuronopathic Gaucher)
2. the shared gene and mechanism (GBA1 / GCase, lysosomal)
3. a common disease that shares it (GBA1-associated Parkinson's)
4. its patient and research organizations
5. reusable trials
6. a sourced collaboration brief

For a sparse neighbour (saposin C deficiency), the atlas returns an honest-gap coverage report instead of a guess.

**The winning angle.** The bar is trust plus action, not graph size. Three things to show:
1. **Cited AI.** Every sentence the AI writes cites an edge id, and the edge opens its source record. An AI label on screen says "AI-generated, cites edge e_123".
2. **One real, verifiable story.** Two faulty GBA1 copies cause Gaucher disease. One faulty copy is a Parkinson's risk factor (Monarch `contributes_to` MONDO:0008199, OMIM-sourced [V]). An N370S or L444P variant was found in 15% of Ashkenazi Jewish PD patients vs 3% of non-Ashkenazi patients (Sidransky 2009, PMID 19846850 [V]). The PD side has reusable assets:
   - ASPro-PD, NCT05778617: phase 3 ambroxol trial, 330 participants, about half GBA1 carriers, recruiting [V].
   - PR001 / LY3884961: the same gene therapy is in trials for GBA1-PD (NCT04127578) and for Gaucher type 2 (NCT04411654) [V].
   - An ambroxol registry already enrols both communities (NCT04388969) [V].
3. **Counterexamples and contradictions on screen.**
   - Venglustat failed in GBA1-PD: MOVES-PD was terminated after missing its endpoints (PMID 37479372 [V]). It met its primary endpoints in Gaucher type 3 (LEAP2MONO, Sanofi 2026-02-02 [V]). Same mechanism, different outcome.
   - The PSAP link to PD susceptibility is curated in OMIM but contested in replication letters [V].

**OpenAI is a visible first pillar** (Section 8a): Extract, Reconcile, Explain and semantic search all run on OpenAI. We use the Responses API with structured outputs, the Batch API, and embeddings. All outputs are precomputed into the snapshot, so the demo survives an API outage.

**We will NOT build:** a whole-world graph; a Neo4j or other database server; user accounts; live crawling of patient-org sites; full-text PMC mining; investor/RFA intelligence; a chat agent as the main UI; multiple clusters. The 1-minute video will show none of these.

---

## 2. Problem digest

### 2.1 The brief, distilled
- Maria's three questions: *Who shares our disease characteristics? What useful work already exists? What should we do together next?*
- The key insight: organize by **mechanism + phenotype**, not by name. Same gene can mean a different mechanism; different genes can share one.
- Module 1 is the graph builder with sourced, dated, confidence-scored edges. Module 2 is the trust layer: observed vs inferred, contradictions, and "no supported route? say so". Module 3 is action: mechanistic overlap clusters, shareable assets, and network overlap (shared KOLs).
- 24h ambition: **one complete journey, disease -> connection -> shared action, or an honest gap**, plus a 10x case and what must be validated next.
- Must use OpenAI models/tools to be eligible for track prizes.

### 2.2 How each judging criterion is scored by evidence in our demo

| Criterion | What judges look for | Concrete proof in our demo | Owner |
|---|---|---|---|
| Graph quality | Node/edge design, defensible clusters, useful paths, counterexamples, uncertainty | Typed graph with CURIE ids. Cluster view where each membership lists its top shared HPO terms and GO terms. "Same mechanism, different outcome" card for venglustat (GBA1-PD vs GD3). "Hypothesis only" labels on literature-only neighbours (SMPD1-PD, contested PSAP-PD) | Ali |
| Evidence integrity | Sourced, cross-checked; data vs hypothesis vs clinical proof | Edge panel shows source link, retrieved date, evidence type badge (observed / curated / inferred-hypothesis), the confidence rubric reasons, and `contradicted_by`. Trial status badges (recruiting / terminated) | Ali + B |
| Patient progress | Diagnosis -> justified collaboration -> reusable asset -> next milestone | Action view for neuronopathic Gaucher. Partners: Gauchers Association / International Gaucher Alliance, plus the GBA1-PD research community (MJFF GBA1-PD Catalyst, Cure Parkinson's). Assets: ASPro-PD, the ambroxol registry NCT04388969, PR001 trials. Next step: a collaboration brief, plus an expert-check list | C |
| 10x impact | Milestone, existing timeline vs ours, assumptions | Milestone: "a Gaucher group launches a collaboration that reuses GBA1-PD trial infrastructure, biomarkers and safety data". 10x is on the find-mechanism / asset / partner step, with assumptions stated (Section 13) | Ali + C |
| Ambition & product craft | Intuitive, collaboration at scale | One global search, progressive reveal, low-ink design, the AI label on every generated sentence, the honest-gap card | C |

### 2.3 Traps to avoid
| Trap | Guardrail |
|---|---|
| Unsourced edges | The Pydantic model rejects an edge without provenance. A loader test asserts that 100% of edges have `source_record_id` and that 100% of non-analytics edges have a URL. |
| LLM-hallucinated links or ids | Extract keeps a claim only if its quote appears verbatim in the abstract. Reconcile can only choose from candidate ids. Explain must cite edge ids on the path, and a validator rejects anything else. |
| Too-broad scope | One cluster of 9-12 diseases. Hard feature freeze at T+20. |
| A pretty graph with no action | The demo ends in the action view and the proposal, not in the graph. |
| Hiding uncertainty | Inferred edges are dashed and labelled "hypothesis". The contradiction chip is visible without a click. |
| Overclaiming | No efficacy claims about ambroxol, venglustat or gene therapy. Trials are described by registry fields only. Dose differences are shown as research evidence, never as dosing advice. "No approved therapy" is shown with its date (the venglustat NDA for GD3 has an FDA target date of 2026-11-25 [U: press coverage]). |
| Demo dies on API or cold start | Precomputed Explain cache in the snapshot, static JSON fallback in the frontend, and the backend warmed before recording |

---

## 3. Product definition

### 3.1 Personas, prioritized
| Priority | Persona | How served | Cost |
|---|---|---|---|
| 1 | **Maria** (patient org leader) | Full golden journey: search -> path -> cluster -> action view -> proposal | Main build |
| 2 | **Devon** (new caregiver) | Same search box with synonym resolution. A "Plain language" toggle on Explain output. Honest-gap card says "no group found; closest communities are X, Y" | Near zero, reuses Explain |
| 3 | **Dr. Osei** (researcher) | A "Who works on this mechanism" list: RePORTER PIs and PubMed authors grouped by gene, with a shared-investigator badge for people who span two genes | Small (one endpoint plus a list) |
| 4 | **Priya** (pharma scout) | A "Mechanism lens" dropdown, e.g. "pharmacological chaperone" or "glucosylceramide synthase inhibition", that ranks diseases by mechanism evidence, org presence, assets and unmet need | Should-have. Cut first |

### 3.2 Golden demo journey (Maria, neuronopathic Gaucher)
Maria leads a family group for **neuronopathic Gaucher disease**:
- Type 2: MONDO:0009266, OMIM:230900, 51 HPO annotations [V]
- Type 3: MONDO:0009267, OMIM:231000, 50 HPO annotations [V]

Enzyme replacement does not cross the blood-brain barrier. As of 2026-10-03 there is no approved therapy for the neurological disease (Sanofi press release, 2026-02-02 [V]). Venglustat for GD3 is under FDA review, with a target date of 2026-11-25 [U: press coverage, not fda.gov]. The UI shows this as dated status, not a timeless claim.

| Step | Screen | Graph evidence (edge type, source) |
|---|---|---|
| 1 | Search "Gaucher" (or "GBA", the old symbol). Results show the disease grouping, the types and the gene | Node synonyms from MONDO + HGNC (GBA is a previous symbol of GBA1 [V]) |
| 2 | Disease card for type 3: cause, key phenotypes ranked by information content (supranuclear gaze palsy, myoclonus, ataxia, seizures), mechanism | `caused_by` GBA1 (OMIM via Monarch, curated). `has_phenotype` (HPO, curated) |
| 3 | Mechanism hop: GBA1 -> GCase / lysosomal glucosylceramide degradation | `participates_in` (GO annotations, curated) [U: pick the exact GO terms at ingest] |
| 4 | Related disease: GBA1 -> late-onset Parkinson disease (MONDO:0008199). The card shows "one faulty copy raises PD risk", with 15% (Ashkenazi Jewish) vs 3% (other ancestries) for two common variants, and 7% with full sequencing | `contributes_to` (OMIM via Monarch [V]). Publication edge, Sidransky 2009, PMID 19846850 [V] |
| 5 | Organizations: The Gauchers Association and the International Gaucher Alliance on the Gaucher side; the MJFF GBA1-PD Research Catalyst and Cure Parkinson's on the PD side | `represents` / `funds` (curated, `data/curated/organizations.yaml`) |
| 6 | Reusable assets: ASPro-PD NCT05778617 (phase 3, ambroxol, 330, recruiting). Narita 2016 nGD ambroxol pilot (PMC4774255). Ambroxol registry NCT04388969 (both populations). PR001 in PD (NCT04127578) and in Gaucher type 2 (NCT04411654) | `studies_condition` (CT.gov, observed). Publication (curated) |
| 7 | "What differs" panel (see below) | Eligibility and arm fields (CT.gov). Publication fields |
| 8 | Collaboration brief (Explain): a plain-language draft to the ASPro-PD investigators and the MJFF GBA1-PD programme. Asks: can nGD studies reuse the safety data, the GBA1-stratified design and the biomarker protocols? Every sentence cites edge ids; it lists expert-review questions | Explain output with edge citations and the "AI-generated" label |
| 9 | Hypothesis hop: GBA1 -> GCase trafficking -> SCARB2 (LIMP-2) -> action myoclonus-renal failure. Dashed and labelled "hypothesis" | SCARB2 `gene_associated_with_condition` Gaucher type I (Orphanet via Monarch [V]). LIMP-2 targets GCase to the lysosome, Reczek 2007, PMID 18022370 [V], extracted, `inferred` |
| 10 | Counterexample card: venglustat was negative in GBA1-PD (MOVES-PD) and positive in GD3 (LEAP2MONO) | CT.gov `whyStopped` [V]. PMID 37479372 [V]. Sanofi release [V] |

What the step 7 panel shows. All of it is research evidence from the sources, not dosing advice.

| | ASPro-PD | Narita 2016 nGD pilot |
|---|---|---|
| Population | Adults 35-75 with PD, GBA1 carriers and non-carriers | Patients with neuronopathic Gaucher disease, on ERT |
| Dose | Fixed, titrated to 1260 mg/day | Weight-based target of 25 mg/kg/day, max 1300 mg/day |
| Endpoints | MDS-UPDRS at 104 weeks | Myoclonus, seizures, CSF glucosylsphingosine |
| Design | Placebo-controlled | Open-label, n=5 |

**Next experiment, stated as a hypothesis:** does the ASPro-PD biomarker protocol include GCase activity or lyso-Gb1 [U]? If so, a shared readout could link PD carrier data with nGD natural-history data from the ICGG registry (NCT00358943).

### 3.3 Honest-gap journey (saposin C deficiency)
1. Search "saposin C". The result is Gaucher disease due to saposin C deficiency (MONDO:0012517, OMIM:610539, 36 HPO terms [V]). The mechanism edge exists: PSAP `causes` (OMIM via Monarch [V]). GCase is normal, but its activator is missing.
2. The coverage report shows the counts searched [V]:
   - 0 ClinicalTrials.gov condition matches
   - 0 NIH RePORTER projects
   - 20 PubMed records
   - no dedicated patient organization (NORD and Global Genes have disease pages only)
   - one source says "no specific therapy is approved" (PMID 41812503)
3. Weak lead (hypothesis): one patient treated with eliglustat for 9 years improved systemically but not in seizures. Venglustat is a brain-penetrant drug of the same class, positive in GD3.
4. Next question: "Would GD3 venglustat investigators or the ICGG registry include saposin C deficiency patients? Contact the IGA to find families."

### 3.4 MoSCoW (24h)
| Must | Should | Could | Won't |
|---|---|---|---|
| Snapshot built by `make data` (MONDO subset, HPO annotations, gene-disease, GO, CT.gov, curated orgs/assets, PubMed abstracts) | RePORTER PIs + shared-investigator bridges | Priya ranking view | Whole-world graph |
| OpenAI Extract on about 300-600 abstracts with quote verification | Phenotype similarity via Resnik best-match average | Patient "contribute evidence" form (writes to a pending queue) | Auth / accounts |
| OpenAI Reconcile (embeddings + structured choice) | Contradiction detection from extracted polarity | Burden-of-care tab (shared symptom management) | Neo4j |
| Explain with edge-id validator, precomputed for demo paths | Live Explain for arbitrary paths, rate-limited | Reactome pathways in addition to GO | PMC full text |
| Search, node, neighbors, path, cluster, coverage endpoints | Edge panel shows confidence rubric reasons | Clinic/KOL map | Investor/RFA signals |
| UI: search -> path view -> edge panel -> action view -> gap card | Cluster graph visualization (force layout) | | Mobile-perfect UI |
| Deployed (Vercel + Render) plus `docker compose` | Small extraction gold set (30 abstracts) with precision reported | | |
| README: architecture, OpenAI section, dataset reproduction; 1-min video | | | |

---

## 4. Disease cluster: decision and seed list

**Decided (A1, issue #14, 2026-10-03): the GBA1/GCase–lysosomal dysfunction cluster (Gaucher / GBA1 -> Parkinson's, plus lysosomal neighbours).**

**Rationale:** We chose the GBA1/GCase–lysosomal dysfunction cluster for three reasons. Neuronopathic Gaucher has a real neurological treatment gap. GBA1/GCase gives a biologically strong link to Parkinson's. And Parkinson's acts as our validated anchor. We are not claiming to discover that known link. We use it to validate the system, then search the same gene-pathway-phenotype neighbourhood for less obvious diseases, assets, researchers and evidence gaps.

- Rationale and alternatives: [ADR 0003](adr/0003-demo-cluster-gaucher-gba1.md).
- Full verified seed list (MONDO, ORPHA, OMIM, HGNC, HPO, NCT, orgs, gap evidence): [DATA_SOURCES.md](DATA_SOURCES.md#demo-cluster-gaucher--gba1---parkinsons).
- Curated records: `data/curated/organizations.yaml` and `data/curated/assets.yaml`.

### 4.1 Candidates compared
| Criterion | **Gaucher / GBA1 -> PD (chosen)** | Presynaptic SNAREopathies (alternative) | Lysosomal: NCL / CLN family | CDG (PMM2-CDG etc.) |
|---|---|---|---|---|
| Mechanism story | One gene, two diseases: recessive Gaucher, and dominant PD risk. Lysosomal neighbours (PSAP, SCARB2, SMPD1, ATP13A2, CTSD, GBA2) | Different genes, one process (vesicle fusion). A name-hides-mechanism case (SNAP25 = "CMS18") | Shared lysosomal clearance | One glycosylation pathway |
| Public data | 50-92 HPO terms per Gaucher entry. OMIM + Orphanet gene-disease edges in Monarch [V] | Rich (46-77 HPO terms for the main members [V]) | Rich | Moderate |
| Patient orgs | Gaucher: NGF, IGA, Gauchers Association. PD: MJFF, Cure Parkinson's, Parkinson's UK [V] | STXBP1 Foundation, SynGAP Research Fund, SLC6A1 Connect [V] | BDSRA and others | CDG CARE [U] |
| No approved therapy for hero | Yes for the neurological disease, as of 2026-10-03 [V]. Venglustat GD3 FDA decision expected 2026-11-25 [U] | Yes [U, low risk] | CLN2 has cerliponase alfa | PMM2: none [U] |
| Reusable assets | ASPro-PD; ambroxol registry spanning both communities; PR001 in PD and GD2; ICGG registry; GOS [V] | Multi-gene NHS NCT06555965; NCT06625112; NCT04937062 [V] | Many registries | Frontiers in CDG NHS [U] |
| Counterexample | Venglustat: negative in GBA1-PD, positive in GD3 [V] | SNAP25 label; CAP-002 terminated [V] | Weak | Weak |
| Honest-gap candidate | Saposin C deficiency: 0 trials, 0 RePORTER projects [V] | CPLX1 (0 trials [V]) | Weak | Several |
| 10x lever | Rare community borrows from a large, funded common-disease programme | One sponsor adds a gene to a running study | Registry reuse | Pathway reuse |

**Why Gaucher/GBA1:** it is the only candidate with a rare-to-common bridge, so the reusable assets are large, funded and already GBA1-stratified. It also has assets that span both communities today, a well-documented counterexample, and a one-hop honest gap.

**Documented alternative:** presynaptic SNAREopathies, with the seed data below kept from the earlier recommendation. Switch only if the GBA1 seeds fail at G1.

### 4.2 Seed entities (summary; IDs verified 2026-10-03)
| Disease (MONDO) | Xrefs | Gene (HGNC) | Role in demo |
|---|---|---|---|
| MONDO:0009266 Gaucher type II; MONDO:0009267 Gaucher type III | OMIM:230900, 231000; ORPHA:77260, 77261 | GBA1 (HGNC:4177) | **Hero (Maria)** |
| MONDO:0009265 Gaucher type I; MONDO:0011945 perinatal lethal | OMIM:230800, 608013 | GBA1 | Context (type I has approved therapy) |
| MONDO:0008199 late-onset Parkinson disease | OMIM:168600; ORPHA:411602 | GBA1 `contributes_to` | **Partner disease** |
| MONDO:0012517 Gaucher due to saposin C deficiency | OMIM:610539; ORPHA:309252 | PSAP (HGNC:9498) | **Honest gap** |
| MONDO:0859183 PD 24 susceptibility | OMIM:619491 | PSAP | Contested hypothesis |
| MONDO:0009699 action myoclonus-renal failure | OMIM:254900; ORPHA:163696 | SCARB2 (HGNC:1665) | Hypothesis hop (GCase trafficking) |
| MONDO:0009756 / MONDO:0011871 Niemann-Pick A / B | OMIM:257200, 607616 | SMPD1 (HGNC:11120) | Neighbour; PD link is literature-only (PMID 30788890) |
| MONDO:0011706 Kufor-Rakeb syndrome | OMIM:606693; ORPHA:306674 | ATP13A2 (HGNC:30213) | Neighbour: lysosomal and parkinsonism |
| MONDO:0012414 NCL 10 | OMIM:610127; ORPHA:228337 | CTSD (HGNC:2529) | Neighbour |
| MONDO:0013737 SPG46 | OMIM:614409; ORPHA:320391 | GBA2 (HGNC:18986) | Neighbour (same substrate) |

Key trials: NCT05778617, NCT04388969, NCT04127578, NCT04411654, NCT05222906, NCT02906020, NCT05819359. Registries: NCT00358943 (ICGG), NCT03291223 (GOS). Key literature: PMID 27042680 (Narita 2016), 19846850 (Sidransky 2009), 37479372 (MOVES-PD), 18022370 (LIMP-2), 41812503 (saposin C and eliglustat).

**Correction to the original brief for this task:** PMC4351661 (Gan-Or 2015) does not state "15% vs 3%". Cite Sidransky 2009 for those figures.

### 4.3 Alternative kept on file: presynaptic SNAREopathies (verified 2026-10-03)
| Disease (MONDO) | Xrefs | Gene (HGNC) | Notes |
|---|---|---|---|
| MONDO:0032900 VAMP2 NDD | OMIM:618760 | VAMP2 (HGNC:12643) | Would be the hero; 15 HPO terms; no org found |
| MONDO:0012812 DEE 4 | OMIM:612164, Orphanet:599373 | STXBP1 (HGNC:11444) | NCT06555965, NCT06625112, NCT04937062, NCT06983158 (terminated) |
| MONDO:0033864 Baker-Gordon syndrome | OMIM:618218 | SYT1 (HGNC:11509) | Phenotype neighbour |
| MONDO:0014590 CMS18 | OMIM:616330 | SNAP25 (HGNC:11132) | Name hides mechanism |
| MONDO:0033372 DEE 63 | OMIM:617976 | CPLX1 (HGNC:2309) | Honest gap (0 trials) |
| MONDO:0012960 / MONDO:0014633 | OMIM:612621 / 616421 | SYNGAP1 / SLC6A1 | Bridges |

Sources: Monarch API v3, ClinicalTrials.gov v2, DisMech "Synaptic Vesicle Cycle Disorders" grouping.

---

## 5. Data plan

### 5.1 The big shortcut
The **Monarch KG and API v3** already join MONDO, HPO, HGNC and OMIM-derived gene-disease links, with `primary_knowledge_source` on every association [V: `infores:omim` returned]. For a 9-12 disease slice, **API calls take minutes**. The bulk KG is 343 MB tar.gz [V] and is not needed. Use bulk files only where we need IC over the whole corpus (phenotype.hpoa).

### 5.2 Per-source table
| Source | Access (verified) | Auth / rate | License | Size | Ingest for slice | Edges | Prio | Fallback |
|---|---|---|---|---|---|---|---|---|
| Monarch API v3 | `GET /v3/api/search`, `/entity/{id}`, `/entity/{id}/biolink:CausalGeneToDiseaseAssociation` [V] | none; be polite (no published limit found [U]) | Monarch open; per-source licences flow through [U] | n/a | 15 min | `caused_by`, synonyms, xrefs | P0 | Commit the JSON responses to `data/raw` |
| MONDO | `purl.obolibrary.org/obo/mondo.json` [V] | none | CC BY 4.0 [U] | 107 MB [V] | 10 min (subset by IDs) | disease nodes, synonyms, xrefs | P0 | Monarch entity endpoint |
| HPO | `phenotype.hpoa` (35.8 MB, 2026-09-02) + `hp.json` (21.9 MB) from GitHub releases [V] | none | HPO license, free with attribution [U: hpo.jax.org/license 404'd] | 58 MB | 20 min. **Whole-file IC** (all diseases) for weighting | `has_phenotype` (with frequency), IC per term | P0 | Monarch `DiseaseToPhenotypic` association endpoint |
| HGNC | `hgnc_complete_set.txt` (17 MB, 2026-10-02) [V] | none | free [U] | 17 MB | 5 min | gene nodes, symbol synonyms | P0 | Monarch gene entity |
| GO annotations | `goa_human.gaf.gz` (15 MB) [V] | none | CC BY 4.0 [U] | 15 MB | 10 min (+GO closure via `go-basic.obo` [U]) | `participates_in` gene->mechanism | P0 | Curated 3-term mechanism list |
| ClinVar | E-utilities esearch/esummary per gene [V]; bulk `variant_summary.txt.gz` is 451 MB [V], avoid | 3 rps without key, 10 rps with `NCBI_API_KEY` [U: from NCBI docs NBK25497] | public domain [U] | ~1-2 MB for slice | 20 min | `has_variant`, P/LP counts, review status, molecular consequence -> LoF hint | P0 (counts) / P1 (variant nodes) | Counts only on the disease card |
| ClinicalTrials.gov v2 | `/api/v2/studies?query.cond=` and `/studies/{nct}` [V] | none; about 50 req/min [U] | public domain [U] | <1 MB | 15 min | `studies_condition`, `tests_intervention`, status, eligibility | P0 | Commit the JSON |
| PubMed | E-utilities esearch + efetch (abstracts XML) [V esearch] | as ClinVar | Abstracts may be copyrighted: store PMID, short quote, extracted facts [U] | ~2-4 MB | 30 min (about 600 abstracts) | `publication`, `authored_by`, Extract claims | P0 | Europe PMC REST [U] |
| NIH RePORTER v2 | `POST /v2/projects/search` [V] | no key; **max 1 request/second** [V doc] | public [U] | <1 MB | 15 min | `funds`, `works_on`, investigator nodes | P1 | Skip; Osei list uses PubMed authors |
| Orphadata | `en_product1.xml` (nomenclature/xrefs), `en_product6.xml` (genes, with PMIDs) [V reachable] | none | CC BY 4.0 [V via search summary; re-check] | product6 is tens of MB [U] | 20 min | ORPHA xrefs, gene-disease cross-check (+0.05 confidence) | P1 | MONDO xrefs only |
| Orphanet patient orgs / NORD / Global Genes / EURORDIS | No free bulk API found; Orphanet's directory is not in the free products [U] | site terms | per site | tiny | **Manual curation** into `data/curated/orgs.yaml` with URL + date, about 1.5 h | `represents`, `operates` | P0 (curated) | Mark the org as "not found" and send it to the gap report |
| OMIM API | key needed; redistribution restricted [U] | key | restricted | | Do not ingest. OMIM-sourced links come via Monarch with `infores:omim` attribution | | P2 | Monarch |
| Reactome | `NCBI2Reactome_All_Levels.txt` [V reachable] | none | CC BY 4.0 [U] | ~100 MB [U] | 15 min | pathway nodes | P2 | GO only |
| DisMech (Monarch) | static pages [V] | none | [U] | | 10 min | seed list only. AI-curated, so mark as `curated` with a lower base (0.6) | P1 | none |
| JAX models, RareConnect, bioRxiv | | | | | | | P2 | none |

### 5.3 `make data` design
```
make data            -> uv run python -m atlas.pipeline all --slice data/slices/gba1.yaml
  1 fetch      data/raw/<source>/<YYYY-MM-DD>/...  (cached; skip if present; --refresh to refetch)
  2 normalize  per-source parsers -> data/interim/*.jsonl  (Node/Edge models, deterministic)
  3 extract    OpenAI Batch job over abstracts -> data/interim/extract/*.jsonl (cached by input hash)
  4 reconcile  exact/synonym match -> embeddings top-k -> OpenAI choice (cached)
  5 build      graph + rubric + contradictions + analytics (clusters, similarity, bridges)
  6 explain    precompute demo paths + node summaries -> explain_cache.json
  7 snapshot   data/processed/atlas-<date>/{nodes.json, edges.json, clusters.json, coverage.json,
               explain_cache.json, manifest.json}
make data-offline    -> steps 5-7 only, from committed interim + LLM cache (no keys, no network)
```
- **Commit** the slice config, `data/curated/*.yaml`, the LLM response cache (JSONL, small) and the final snapshot (estimated <10 MB). Do **not** commit the big raw dumps. The manifest records each source URL, version/Last-Modified, retrieval time, models, prompt versions and `rubric_version`.
- A judge reproduces the snapshot with `make data-offline` (deterministic, no key), or runs the full pipeline with `make data` and an `OPENAI_API_KEY`.
- The snapshot ships **inside the backend Docker image**. Release assets add a dependency for no gain.

---

## 6. Graph and evidence model

### 6.1 Changes needed to `backend/src/atlas/models/evidence.py` and `docs/EVIDENCE_MODEL.md`
| Change | Why |
|---|---|
| Add `Edge.id`: deterministic `e_` + sha1(source, target, relation, provenance.source, source_record_id)[:12] | Explain cites edge ids. `contradicted_by` needs targets |
| Add `Provenance.source_version`, `evidence_quote`, `extractor: {model, prompt_version}`, `supporting_edge_ids` | Already listed as "planned" in EVIDENCE_MODEL.md. Required for Extract and analytics edges |
| Require `url` unless `source == "analytics"` (model validator) | Evidence integrity |
| Add `Edge.qualifiers: dict[str, str]` (HPO frequency, ClinVar clinsig/review status, polarity, trial status) | Avoids new fields per source |
| Add `Edge.confidence_reasons: tuple[str, ...]` | Shows the rubric on screen ("curated KB 0.90; +0.05 Orphanet agrees") |
| Add `Node.xrefs`, `Node.attributes` (IC for phenotype; status/phase/enrollment for study; url for org) and `Node.description` | Cards need them |
| `NodeType`: add `CLUSTER`, or keep clusters out of nodes in `clusters.json`. **Recommend keeping them out of nodes** | Simpler; `in_cluster` becomes a node attribute |
| Add relation `participates_in` (gene -> mechanism/GO) to the edge table | GO-sourced mechanism |
| Add `StudyStatus` labels to separate **clinical proof** (completed with results / approved) from observational studies | The brief asks to separate data, hypothesis and clinical proof |

### 6.2 Confidence rubric
Keep the EVIDENCE_MODEL.md rubric as-is, with these additions:
- GO annotations: 0.90 for experimental evidence codes (EXP/IDA/IMP/IGI), 0.70 for IBA/IEA.
- DisMech base 0.60.
- Curated org pages 0.60.

LLM self-confidence is never used. Rubric version `r1`.

### 6.3 Observed / curated / inferred and contradictions
- Observed: CT.gov, RePORTER, ClinVar submissions. Curated: Monarch/OMIM, HPO, GO, Orphanet, team curation with URL. Inferred: Extract claims and all analytics edges, drawn dashed and labelled "hypothesis".
- Contradictions are detected two ways:
  - Extract polarity `contradicts` on the same (subject, relation, object).
  - Same gene with different `has_mechanism` values. Seed cases: PSAP-PD susceptibility (Oji 2020, PMID 32201884, vs replication letters such as PMID 33793763) and venglustat (negative in GBA1-PD, positive in GD3). If Extract does not surface them, add curated contradiction pairs with their PMIDs, which a team member must read and verify.
- Paths through a contradicted edge are flagged, and Explain must mention the contradiction (the validator checks this).

### 6.4 Coverage report
Per disease: sources searched, with query and record count. Example: "ctgov: query.cond=saposin C deficiency -> 0". The report also lists what is missing (org, study, mechanism evidence, variant-effect evidence), weak leads (paths with min confidence < 0.4) and templated next questions. Explain rewrites them in plain language and cites coverage ids.

---

## 7. Analytics

| Component | Method | 24h feasible? |
|---|---|---|
| Phenotype similarity | IC from the **whole** phenotype.hpoa (IC = -log p(term or descendant annotated)). Score = IC-weighted Jaccard over propagated term sets. Store the top 5 shared terms by IC | Yes (about 1.5 h). Resnik BMA is a Should |
| Mechanism similarity | Jaccard over gene -> GO BP closure, restricted to a curated whitelist of about 30 lysosomal / sphingolipid terms to avoid generic terms like "protein binding" | Yes (about 1 h) |
| Variant-effect signal | `MECH:` labels from Extract and ClinVar molecular consequence. Pairs with conflicting mechanisms on the same gene get **negative** weight -> counterexample card | Partial. Present as hypothesis |
| Combined weight | `w = 0.5*pheno + 0.4*mech + 0.1*shared_asset`. kNN (k=4) above threshold 0.15 | Yes |
| Community detection | `networkx.community.louvain_communities(seed=42)` on the disease-disease graph. Expect 2-3 groups: the glucosylceramide core (Gaucher types, saposin C deficiency, SPG46), other lysosomal storage (Niemann-Pick A/B, NCL10, AMRF), and parkinsonism (GBA1-PD, Kufor-Rakeb) | Yes. With about 12 nodes this is near-trivial, so we explain memberships rather than claim scale |
| Bridges | Betweenness on the combined graph. Plus "shared asset bridges" (a study whose conditions span two genes, e.g. NCT06555965) and "shared investigator bridges" (the same RePORTER profile_id or PubMed author linked to 2+ genes) | Yes for assets. Investigators are a Should |
| Priya ranking | For a mechanism m: score = mech_evidence(m) x (1 + has_org) x (1 + n_assets) x unmet_need (no approved therapy = 1). Shown with columns, not a black box | Could |

Defensibility: the cluster card says "in cluster because: shares glucosylceramide catabolism (GBA1, PSAP; curated) and 4 high-IC HPO terms; GBA1-PD is linked by the gene, not by phenotype similarity".

---

## 8. AI layer

### 8a. OpenAI usage (judging requirement): a first-class pillar
**Rule:** every model call in the product goes to OpenAI. No other LLM provider is in the code, dependencies or docs. A unit test greps `backend/src` for any non-OpenAI LLM SDK import and fails if it finds one.

**Verified model catalogue (developers.openai.com, read 2026-10-03):**
- Current flagship family: `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6-luna` (https://developers.openai.com/api/docs/models) [V].
- Prices per 1M tokens, standard input / cached input / output (https://developers.openai.com/api/docs/pricing) [V]:
  - gpt-6-astra: $10 / $1 / $50
  - **gpt-6.1-sol: $2.00 / $0.10 / $10.00**
  - **gpt-6-luna: $0.10 / $0.01 / $0.50**
  - gpt-5.4-mini: $0.75 / $0.075 / $4.50
  - gpt-4.1-mini: $0.40 / $0.10 / $1.60
- **Batch tier is 50% off** (Sol: $1 / $5; Luna: $0.05 / $0.25) [V].
- Embeddings: text-embedding-3-small $0.02, -large $0.13 [V].
- gpt-6.1-sol: structured outputs, function calling, web search and file search are all supported. 1.05M context, 128k output, knowledge cutoff 2026-04-30 [V model page].
- gpt-6-luna: 1.05M context, cutoff 2026-05-18 [V]. **Structured-outputs support not confirmed on its page [U]. Test this first at T+1.**
- A life-sciences model, `gpt-rosalind-research` ($5 / $0.50 / $25), appears on the pricing page [V]. Access requirements are unknown [U]. Optional experiment only; never on the critical path.

**Feature -> model / API map (recommended):**
| Feature | Model | API / tool | Why |
|---|---|---|---|
| Extract (abstract -> claim edges) | `gpt-6.1-sol`, low reasoning effort [U: parameter name in Responses API] | **Batch API** + Responses API **structured outputs** (strict JSON schema) | Quality matters most here. Batch halves cost, and the turnaround fits a T+4..T+8 window [U: batch SLA up to 24h; submit early and keep a synchronous fallback] |
| Reconcile, step 1 | `text-embedding-3-small` | Embeddings API | Synonym and semantic match over MONDO/HPO/HGNC labels and synonyms |
| Reconcile, step 2 (ambiguous only) | `gpt-6-luna` (fallback `gpt-5.4-mini`) | Responses API, structured output, enum of candidate ids | Cheap, high volume. Can only choose from the candidates |
| Explain (path -> plain language, proposal, gap narrative) | `gpt-6.1-sol` | Responses API structured output `{steps:[{text, edge_ids}], uncertainties, next_question}`. Precomputed with prompt caching | Fluency and faithfulness for families |
| Semantic search box | `text-embedding-3-small` | Embeddings computed at build time and stored in the snapshot (NumPy). Query embedding live, with lexical fallback | Devon's lay-language queries, e.g. "jerky movements" maps to an HPO term |
| "Ask the atlas" (Could) | `gpt-6.1-sol` | Function calling over our own API (`search`, `neighbors`, `path`, `coverage`). Answers must cite edge ids | Optional agentic layer. Agents SDK only if time remains [U] |
| Extraction evaluation | `gpt-6.1-sol` as a grader is not used; humans label the gold set | | Avoids self-grading bias |

**Backend config change (flag for review):** `DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"` in `backend/src/atlas/config.py` is two generations old. Replace it with four settings:
- `OPENAI_MODEL_EXTRACT=gpt-6.1-sol`
- `OPENAI_MODEL_RECONCILE=gpt-6-luna`
- `OPENAI_MODEL_EXPLAIN=gpt-6.1-sol`
- `OPENAI_EMBED_MODEL=text-embedding-3-small`

Keep `OPENAI_MODEL` as a single override. Update `.env.example` and the README env table. If Luna fails the structured-output smoke test, set Reconcile to `gpt-5.4-mini`.

**How judges see OpenAI usage:**
1. In the UI, every generated sentence carries a small label: "AI-generated (OpenAI gpt-6.1-sol) - cites e_7f3a, e_91bc". Clicking the label opens the edges. Extracted edges show "Extracted by OpenAI from PMID:xxxx" with the quote.
2. The architecture diagram has an "OpenAI" swimlane with three boxes: Extract (Batch + structured outputs), Reconcile (embeddings + Luna), Explain (Sol). It goes in the README and in the video.
3. The README gets a section "Built with OpenAI" with the model table above, call counts and cost from the manifest, and the guardrails.
4. `/api/v1/meta` returns `openai: {models, calls, tokens, cost_usd, prompt_versions}` from the manifest. The footer shows "Built with OpenAI. 612 abstracts extracted, 1,840 edges, $X".

**Cost estimate (slice):**
| Job | Volume | Tokens | Model / tier | Est. cost |
|---|---|---|---|---|
| Extract | 600 abstracts | in ~1.3k each (0.8k system/schema, cached) = 0.8M; out ~0.5k incl. reasoning = 0.3M | Sol, Batch | 0.8x$1 + 0.3x$5 = **~$2.3** (~$4.6 synchronous) |
| Reconcile | ~1,500 ambiguous mentions | 0.6M in / 0.1M out | Luna | **~$0.1** |
| Embeddings | MONDO+HPO+HGNC labels/synonyms, full files (~600k strings x ~8 tok) | ~5M | 3-small | **~$0.1** |
| Explain precompute | 60 paths/cards x 3 iterations | 0.6M in / 0.2M out | Sol | **~$3.2** |
| Dev iteration + live demo | | | | **~$15** |
| **Total** | | | | **<$25. Set a project spend cap of $50** |

**Precompute and fallback (the demo must not depend on live calls):**
- The snapshot holds `explain_cache.json`, keyed by sha256(sorted edge ids + prompt_version + model). The API serves cached Explain first. A live call only happens for an uncached path, behind a flag (`EXPLAIN_LIVE=true`), with a 10 s timeout and a per-IP rate limit.
- When the key is missing, rate-limited or erroring, the API returns a **deterministic template explanation** built from edge labels, marked "template (AI unavailable)". This way the UI never shows a blank.
- Semantic search falls back to lexical/synonym search when query embedding fails.
- The frontend bundles a static `demo-fallback.json` for the golden and gap journeys, so the video path works even if Render is down.

### 8b. Extract design
- Input: PMID, title, abstract, and the slice's gene/disease dictionary (for grounding).
- Schema: `claims: [{subject_text, subject_type, relation (enum), object_text, object_type, evidence_quote, polarity: supports|contradicts|hedged, variant_hgvs?}]`, plus `investigators` taken from PubMed metadata (no LLM needed).
- Guardrails:
  - The quote must be found verbatim in the abstract after whitespace normalization.
  - Subject and object must reconcile to a node, or the claim is dropped and logged.
  - Relation must be in the enum.
  - All claims are `inferred`, with base 0.50, or 0.30 if hedged or from a preprint.
- Prompt outline: role (biomedical curator); "extract only what the text states"; allowed relations; examples for LoF, dominant-negative and misfolding; "return an empty list if none".
- Corpus selection: `GENE[tiab] AND (variant* OR patient* OR Gaucher OR Parkinson* OR mechanism)`, 2010+, top 80 per gene. GBA1/PD literature is huge, so filter to GBA/GCase abstracts [U: count hits at ingest].

### 8c. Reconcile design
Deterministic exact match first: label, synonyms and xrefs from MONDO, HGNC and HPO. Then embedding top-5 candidates. Then Luna picks `{chosen_id | none, match: exact|synonym|broader|none, rationale}` from the candidates only. Matches that are `broader` lower confidence by 0.10. Showcase: "GBA" (previous symbol) resolves to GBA1 (HGNC:4177), and "atypical Gaucher" resolves to saposin C deficiency (MONDO:0012517).

### 8d. Explain design
- Input: ordered edges with labels, provenance, evidence type and contradictions.
- Output: steps, each with `edge_ids` (at least 1, all on the path), plus `uncertainties` and `next_question`.
- The validator rejects:
  - any step without an edge id
  - any id that is not on the path
  - numbers that do not appear in the edge attributes
  - a contradicted edge that is not mentioned
- On rejection it retries once, then falls back to the template explanation. A reading-level instruction (about grade 8) covers Devon.

### 8e. Extraction quality evaluation
- Gold set: 30 abstracts (about 3 per gene). Two team members label claims; disagreements are settled by Ali.
- Metrics: claim-level precision (target 0.85 or higher) and recall (report it honestly, likely 0.6-0.7), plus quote-verification pass rate.
- Results are reported in the README and in `/meta`. Prompt v1 vs v2 are compared once if time allows.

---

## 9. Architecture and API

```
Sources --fetch--> data/raw --normalize--> interim --(OpenAI Extract/Reconcile, cached)--> build
   --> snapshot (JSON) --> FastAPI loads into networkx.MultiDiGraph at startup (read-only, immutable)
   --> Next.js (Vercel) --> browser ; Explain cache hit or live OpenAI call (flagged)
```

| Endpoint | Returns | Notes |
|---|---|---|
| `GET /api/v1/search?q=&types=` | ranked nodes + match reason (exact/synonym/semantic) | lexical index plus embeddings |
| `GET /api/v1/nodes/{id}` | node, summary counts, top edges, cluster, coverage status | |
| `GET /api/v1/nodes/{id}/neighbors?types=&min_confidence=&evidence=` | edges + nodes | |
| `GET /api/v1/edges/{id}` | full provenance, rubric reasons, contradictions | |
| `GET /api/v1/paths?from=&to=&k=3` | k best paths. Path cost = sum of -log(confidence); paths with inferred edges are penalized | |
| `GET /api/v1/clusters`, `/clusters/{id}` | members + explanation features + counterexamples | |
| `POST /api/v1/explain` `{edge_ids, audience}` | steps with citations, `source: cache|live|template` | |
| `GET /api/v1/actions/{disease_id}` | partners, assets, differences, next experiment, or coverage report | Maria's action view |
| `GET /api/v1/coverage/{node_id}` | coverage report | |
| `GET /api/v1/meta` | snapshot id, sources, counts, OpenAI usage | exists, extend it |

- Performance: about 2-5k nodes and about 10-20k edges, held in memory. All endpoints should answer in under 50 ms except live Explain.
- Load the snapshot once at startup with FastAPI lifespan. Graph objects are read-only.
- Deploy: Render web service (Docker, snapshot baked in) and Vercel (frontend). The Render free plan sleeps after idle [U: confirm plan; budget about $7 for a non-sleeping instance during judging]. CORS is restricted to the Vercel domain.

---

## 10. UX plan

| Screen | Content | Brief principle |
|---|---|---|
| Home | One search box. Three example chips: "Gaucher", "eye movement problems and myoclonus", "saposin C". The three Maria questions | One global search |
| Disease page | Summary card: cause, top 5 informative symptoms (IC-ranked), mechanism, "who shares this", "what exists", "what next". Depth on click | Progressive reveal |
| Path view | Horizontal chain of chips: disease -> gene -> mechanism -> gene -> disease -> org -> study. Solid edges are data; dashed edges are hypotheses | Low ink, color carries meaning |
| Edge panel (side) | Source link, record id, date, evidence type, confidence + reasons, contradictions (red chip), quote | Explain every edge |
| Cluster view | Small force graph (about 12 nodes) colored by cluster, sized by centrality, with dashed bridges. Counterexample list | Mechanism clusters |
| Action view | Partners, reusable assets (what's reusable vs what differs), expert-review checklist, next experiment, "Draft proposal" (Explain) with copy button | Patient action view |
| Gap card | Searched (sources and counts), missing, weak leads, next question, "help build the missing community" | Honest gap |

Library choices: Tailwind (already in place), `react-force-graph-2d` or `cytoscape` for the cluster view [U: pick at T+8; skip it if it's late, the path view is enough]. Accessibility: color plus label, never color alone.

**1-minute video beats:**
- 0:00-0:08: search "Gaucher"
- 0:08-0:20: path to GBA1-PD via GBA1 / GCase, with the edge panel open on the Sidransky 15% / 3% source
- 0:20-0:28: venglustat counterexample card, plus the dashed SCARB2 hypothesis hop
- 0:28-0:42: action view: ASPro-PD + the ambroxol registry + the Gauchers Association, and the "what differs" panel
- 0:42-0:52: AI collaboration brief with cited edges and the OpenAI label
- 0:52-1:00: saposin C deficiency gap card

---

## 11. Work breakdown

### 11.1 Existing issues mapped
| Issue | Scope adjustment | Owner | Est. |
|---|---|---|---|
| #14 Choose cluster | **Done:** Gaucher/GBA1 -> PD. ADR 0003 written; seed list in DATA_SOURCES | Ali | 0.5 h |
| #15 MONDO + HPO | Via Monarch API + phenotype.hpoa (whole-file IC) | B | 2.5 h |
| #16 ClinVar/OMIM | **Rename:** "Gene-disease (Monarch/OMIM-sourced), GO mechanisms, ClinVar counts". No OMIM API | B | 2 h |
| #17 Orgs, registries, studies | CT.gov ingest + **curated orgs.yaml** | B (CT.gov), C (curation) | 2 h + 1.5 h |
| #18 Extract | Batch + structured outputs + quote verification | Ali | 3 h |
| #19 Reconcile | Embeddings + Luna; promote to **P0** (search depends on it) | Ali | 2 h |
| #20 Clustering + bridges | As in Section 7 | Ali or B | 3 h |
| #21 Trust layer | Rubric, contradictions, coverage | Ali | 2.5 h |
| #22 API | Endpoints in Section 9 | Ali / B | 3 h |
| #23 UI search + cluster | | C | 4 h |
| #24 Edge panel + action view | | C (+Ali) | 4 h |
| #25 Deploy | Move earlier, to a T+6 smoke deploy | Ali | 1 h |
| #26 Moonshot + video | | C + Ali | 2.5 h |
| #27 Checklist | | Ali | 1 h |

### 11.2 Missing issues to add
| New issue | Milestone | Labels | Acceptance criteria |
|---|---|---|---|
| Evidence model v2 (edge id, provenance fields, qualifiers, reasons, url validator) | M2 | type:feat, area:backend, priority:P0 | Models + EVIDENCE_MODEL.md updated in the same PR; tests for the id determinism and url rule |
| Pipeline orchestrator + snapshot loader (`make data`, `make data-offline`) | M2 | type:feat, area:backend, P0 | Clean clone -> `make data-offline` produces an identical snapshot hash; API loads it at startup |
| Curated seed: orgs, registries, assets (`data/curated/*.yaml`) | M2 | type:data, P0 | Each entry has a URL, retrieved date and curator; at least 5 orgs and 6 assets; missing orgs are listed explicitly |
| OpenAI model config split + smoke test | M2 | type:chore, area:backend, P0 | Four env settings; Luna structured-output test passes, or the fallback is documented |
| Extraction gold set + eval script | M3 | type:test, P1 | 30 labelled abstracts; precision/recall printed and stored in the manifest |
| Explain cache + template fallback + offline mode | M3 | type:feat, P0 | With no key set, every demo screen still renders with cited explanations |
| Actions endpoint (`/actions/{id}`) incl. "what differs" | M3 | type:feat, P0 | Gaucher type 3 returns the Gauchers Association / IGA, ASPro-PD and its differences; saposin C deficiency returns a coverage report |
| "Built with OpenAI" README section + UI AI label + /meta usage | M5 | type:docs, P0 | All three visible; numbers come from the manifest |
| Frontend static demo fallback | M4 | type:feat, area:frontend, P1 | Golden and gap journeys work with the backend offline |
| RePORTER investigators + shared-investigator bridges | M3 | type:data, P1 | At least 1 investigator bridge shown or explicitly "none found" |
| No-other-LLM-provider guard test | M2 | type:test, P1 | Test fails on non-OpenAI LLM SDK imports |

### 11.3 Critical path
`#14 cluster -> evidence model v2 -> #15/#16 ingest -> pipeline+snapshot -> #22 API (search/node/path) -> #24 action view -> video`
Extract (#18) and clustering (#20) run in parallel and feed the snapshot. The **demo does not block on Extract**, because the golden path uses curated + observed edges. Extract adds the contradiction and investigator layer.

### 11.4 Workstreams (roles confirmed)
| Person | Role |
|---|---|
| **Ali** (lead, sole approver) | AI layer (Extract/Reconcile/Explain), evidence model, trust layer, API core, deploy. **Also the frontend** (screens, edge panel, action view, gap card, static fallback), with agent help. Reviews every 2-3 h in batches |
| **Sagor** (data/backend) | Ingest connectors (Monarch, HPO, GO, CT.gov, PubMed, RePORTER), analytics, pipeline, tests, verifying every [U] in the seed list |
| **Clara** (limited availability) | Review of the curated YAML (spot-check URLs, about 30 min) and the video narration (async) |

Owners and timings were tracked in GitHub issues and milestones during the hackathon.

PR flow: small PRs, `make check` locally as the gate (Actions are not running), Ali approves with admin bypass. Batch reviews at gates to avoid blocking.

---

## 12. Timeline (T+0 = hackathon start)

| Window | Ali | Sagor | Clara | Gate / checkpoint |
|---|---|---|---|---|
| T+0-1 | Kickoff (20 min): confirm cluster, roles, rules on pre-work. Evidence model v2 PR | Fetch Monarch entities + CT.gov for seeds; commit raw | Curate orgs/assets YAML; wireframes | |
| T+1-3 | OpenAI smoke tests (Sol/Luna structured outputs, embeddings, Batch submit). Config split | HPO (whole-file IC), HGNC, GO ingest | Curation done; UI skeleton (search, disease page) on mock JSON | **G1 T+3: cluster locked, all P0 sources reachable, seeds verified, OpenAI calls working.** If any P0 source fails, use its fallback |
| T+3-6 | PubMed corpus fetch; **submit Extract Batch**; Reconcile pipeline | Normalize -> nodes/edges; snapshot v0; loader | Path view + edge panel on mock data | T+6: smoke deploy of backend + frontend (#25) |
| T+6-9 | Trust layer: rubric, contradictions, coverage | Analytics: IC similarity, GO mechanism, Louvain, bridges | Wire search + disease page to the live API | **G2 T+8: graph slice queryable (search, node, neighbors, path) with real data.** Cut: drop RePORTER, Reactome |
| T+9-12 | Merge Extract results + quote verification; gold-set eval harness | RePORTER (if G2 passed) + investigator bridges; pipeline `make data-offline` | Action view UI; gap card | Sleep rotation starts (each person gets 3-4 h between T+10 and T+18, staggered) |
| T+12-14 | Explain + validator + cache; `/actions` endpoint | Cluster endpoints; tests | Cluster viz (or skip) | **G3 T+14: trust layer + API complete; golden path returns from the API.** Cut: drop cluster viz, Priya view, live Explain |
| T+14-18 | Precompute Explain for demo paths; template fallback; OpenAI README section | Gold-set labelling with Clara; coverage numbers; README dataset section | AI labels, polish, static demo fallback | **G4 T+18: UI journey end-to-end on the deployed URL** (golden + gap) |
| T+18-20 | Bug bash; final `make data`; deploy | Verify every edge link in the demo (10+ spot-checks) | Video script final; screen-capture rehearsals | **T+20 FEATURE FREEZE.** Only fixes after this |
| T+20-22 | Warm backend; record the 1-min walkthrough | Clean-clone reproduction test | Team video record + edit | **T+22: videos done** |
| T+22-23.5 | Submission checklist (#27), README status, rotate keys after judging | Docs pass | Upload, test links in a private window | **T+23.5 SUBMIT** (30 min buffer) |

Cut-lines summary:
- Behind at G1: switch to the SNAREopathy fallback only if GBA1 seeds fail verification; otherwise cut OMIM/Orphadata.
- Behind at G2: Extract runs on 150 abstracts only; drop RePORTER.
- Behind at G3: Explain runs only on precomputed demo paths; drop the cluster visualization (show a cluster list).
- Behind at G4: record from local `docker compose` and keep the deployed URL as best effort, with the static fallback.

---

## 13. 10x moonshot narrative (draft)

**Milestone:** a neuronopathic Gaucher family group launches a research collaboration that reuses GBA1-PD trial infrastructure, biomarkers and safety data. Examples: ambroxol safety data from ASPro-PD, a GBA1-stratified design, and a shared biomarker protocol. This is the step that makes an nGD study designable without starting from zero.

The realistic framing: **10x applies to the early find-mechanism, asset and partner step**. It does not apply to curing anything, or to regulatory timelines.

| Step | Status quo for a small rare community (assumption-based) | Equilibrium route |
|---|---|---|
| Find the shared mechanism and the larger community | Months of conferences, cold emails and literature reading; the GBA1-PD link is well known to specialists but not mapped for families | Minutes: cited path Gaucher -> GBA1 / GCase -> GBA1-PD |
| Find reusable assets | Scattered across registries, press releases and papers | Same session: ASPro-PD, the ambroxol registry spanning both communities, PR001 in both populations, ICGG registry |
| Find partners | Personal networks | MJFF GBA1-PD Catalyst, Cure Parkinson's, IGA, with the evidence for why each is relevant |
| Write a first collaboration brief | Weeks of expert time | A sourced draft for expert review, with "what differs" (population, dose, endpoints, age) already laid out |
| **Total for this step** | **~6-12 months [team estimate]** | **~2-4 weeks including expert review [team estimate]**, about 10x |

Assumptions to state on screen:
1. PD trial sponsors and funders are willing to share protocols, safety data or biomarker methods with a rare-disease group. MJFF's programme explicitly emphasises shared datasets and research assets, but that is not a commitment to Gaucher.
2. PD evidence does not transfer automatically to nGD. Population, age, dose (weight-based in nGD vs fixed in PD), disease severity and endpoints all differ. Venglustat is the reminder that the same mechanism can give opposite results.
3. Regulatory status changes: the venglustat GD3 FDA decision is expected 2026-11-25 [U].
4. Status-quo durations are team estimates [U]. Cite a source if one is found, or label them clearly as estimates.

What must be validated next:
- one expert check of the brief (Gaucher clinician plus PD trialist)
- whether ASPro-PD collects GCase or lyso-Gb1 data [U]
- one contact with the IGA about family interest

---

## 14. Risks and mitigations

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| 1 | Demo breaks live (Render cold start, API down, OpenAI rate limit or key) | M / H | Snapshot baked into the image; Explain cache; template fallback; frontend static fallback; warm-up pinger; paid instance during judging |
| 2 | LLM hallucination or overclaiming (wrong mechanism, invented link) | M / H | Verbatim-quote check; candidate-only ids; edge-id validator; golden path built on curated/observed edges; inferred edges always labelled; gold-set precision reported |
| 3 | Team bandwidth / unknown skills (Sagor, Clara) and Ali as the sole approver bottleneck | H / H | Role fallback table; batch reviews at gates; Ali codes the critical path; curation and video are real deliverables for non-coders |
| 4 | Scope creep (multiple clusters, chat agent, fancy viz) | H / M | MoSCoW + hard freeze at T+20; cut-lines per gate |
| 5 | Data access or licensing surprises (OMIM restrictions, no free org directory, HPO/Monarch terms, Batch SLA) | M / M | No OMIM API (Monarch attribution instead); curated orgs; commit raw JSON; synchronous Extract fallback if the Batch job lags past T+8 |
| 6 | CI not running (Actions blocked) -> broken main | M / M | `make check` before every PR; Ali runs it on merge; no merges without a local green |
| 7 | Mechanism facts wrong (e.g. overstating GBA1-PD as causal, the contested PSAP-PD link, transferring PD dosing to nGD) | M / H | Every mechanism claim is either GO/OMIM-curated or labelled hypothesis; an expert-review checklist is part of the product |
| 8 | Cost overrun | L / L | Spend cap $50; caching; Batch |
| 9 | Hackathon rules on pre-built code/data | U / H | Confirm at kickoff; the repo scaffold is already public and dated |

---

## 15. Open questions and decisions (with recommended defaults)

| # | Decision | Recommended default |
|---|---|---|
| 1 | Disease cluster | **Decided:** Gaucher/GBA1 -> PD (hero nGD, partner GBA1-PD, gap saposin C deficiency); fallback SNAREopathies (ADR 0003) |
| 2 | Sagor's and Clara's skills and roles | **Confirmed:** Sagor = data/backend. Clara has limited availability: curation review and video narration. Ali covers the frontend with agent help |
| 3 | Models | Extract/Explain `gpt-6.1-sol`, Reconcile `gpt-6-luna` (fallback `gpt-5.4-mini`), embeddings `text-embedding-3-small`; retire the `gpt-4.1-mini` default |
| 4 | Live vs precomputed Explain | Precomputed by default; live behind a flag for unseen paths |
| 5 | Snapshot shipping | Baked into the backend Docker image; small snapshot + LLM cache committed |
| 6 | Phenotype similarity | IC-weighted Jaccard; Resnik BMA only if time allows |
| 7 | Pathway source | GO BP (curated whitelist); Reactome is P2 |
| 8 | OMIM | No API; use OMIM-sourced associations via Monarch with attribution |
| 9 | Patient orgs | Manual curation with URL + date; no scraping |
| 10 | Render plan during judging | Pay for a non-sleeping instance for the judging window (about $7) |
| 11 | OpenAI spend cap | $50 on a dedicated project key; rotate after judging |
| 12 | Hackathon pre-work rules / start time / timezone | Confirm at kickoff; set the T+0 clock |
| 13 | Use `gpt-rosalind-research`? | No for the critical path; one optional A/B on Explain if access is open |
| 14 | Cluster visualization library | Path view first; add the force graph only if G3 passes |
| 15 | Who records narration | Clara narrates, Ali drives the screen (to confirm) |
