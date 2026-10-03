# Evidence Model

Status: **draft contract**. It matches the draft in `backend/atlas/models/evidence.py`. The confidence rubric and the coverage report are **planned**. If code and this document disagree, fix one of them in the same PR.

Principle: **no edge without evidence.** Every relationship the atlas shows must answer three questions:
- Who says so?
- How sure are we?
- Is it observed, curated or inferred?

## Node types and ID namespaces

Each node has one stable, namespaced ID. Synonyms and cross-references are stored on the node, not as separate nodes.

| `NodeType` | Primary ID namespace | Example | Cross-refs / fallback |
|---|---|---|---|
| `disease` | MONDO | `MONDO:0009861` | `ORPHA:`, `OMIM:`, `DOID:`, `UMLS:` |
| `gene` | HGNC | `HGNC:1884` | `NCBIGene:`, `ENSG`, `OMIM:` gene entry |
| `variant` | ClinVar Variation ID | `ClinVar:VCV000012345` | HGVS expression, `dbSNP:rs` |
| `mechanism` | Internal controlled vocabulary | `MECH:loss_of_function`, `MECH:lysosomal_enzyme_deficiency` | GO / Reactome IDs when mapped |
| `phenotype` | HPO | `HP:0001250` | |
| `patient_group` | Org slug | `ORG:example-foundation` | Orphanet expert/patient org ID, website URL |
| `publication` | PubMed | `PMID:12345678` | `PMCID:`, `DOI:` |
| `study` | ClinicalTrials.gov | `NCT01234567` | Registry IDs for natural history studies |
| `asset` | Internal | `ASSET:registry/<slug>`, `ASSET:model/<slug>` | JAX strain ID, NCT, URL |
| `investigator` | Internal slug | `INV:<lastname-firstinitial>-<hash>` | ORCID when available, RePORTER PI ID |
| `funder` | Org slug or RePORTER | `FUNDER:nih-ninds`, `REPORTER:<project_number>` (for the grant) | ROR ID |

The example IDs above show the format only. They are not verified facts about any disease. Grants are represented as `asset` or `funder` edges carrying the RePORTER project number in `source_record_id`.

## Edge types

The `relation` field is a controlled string. The direction is `source_id -> target_id`.

| Relation | Source -> Target | Primary data source | Example |
|---|---|---|---|
| `caused_by` | disease -> gene | OMIM, Orphanet, MONDO xrefs | disease `MONDO:...` caused_by `HGNC:...` |
| `has_variant` | gene -> variant | ClinVar | `HGNC:...` has_variant `ClinVar:VCV...` |
| `variant_associated_with` | variant -> disease | ClinVar (with clinical significance) | `VCV...` -> `MONDO:...` |
| `has_mechanism` | variant / gene / disease -> mechanism | OMIM text, ClinVar, Extract | variant -> `MECH:loss_of_function` |
| `has_phenotype` | disease -> phenotype | HPO annotations | `MONDO:...` -> `HP:0001250` (frequency qualifier stored) |
| `shares_mechanism_with` | disease -> disease | Analytics (computed) | `inferred`, the supporting edges are listed |
| `similar_phenotype_to` | disease -> disease | Analytics (IC-weighted HPO) | `inferred`, score and top shared terms stored |
| `in_cluster` | disease -> cluster pseudo-node | Analytics | `inferred` |
| `mentions` / `claims` | publication -> any | PubMed + Extract | `PMID:...` claims (gene has_mechanism LoF) |
| `authored_by` | publication -> investigator | PubMed metadata | `PMID:...` -> `INV:...` |
| `studies_condition` | study -> disease | ClinicalTrials.gov | `NCT...` -> `MONDO:...` |
| `tests_intervention` | study -> asset | ClinicalTrials.gov | `NCT...` -> `ASSET:intervention/...` |
| `funds` | funder -> investigator / asset | NIH RePORTER | `FUNDER:...` -> `INV:...` |
| `works_on` | investigator -> disease / gene / mechanism | RePORTER, PubMed | `INV:...` -> `HGNC:...` |
| `represents` | patient_group -> disease | NORD, Orphanet, Global Genes, org sites | `ORG:...` -> `MONDO:...` |
| `operates` | patient_group -> asset | Org sites, press releases | `ORG:...` -> `ASSET:registry/...` |
| `contradicts` | publication -> edge claim | Extract (polarity = contradicts) | stored through `contradicted_by` on the target edge |

## Provenance

Every edge carries:

| Field | Meaning | Example |
|---|---|---|
| `provenance.source` | Source system | `clinvar`, `hpo`, `pubmed`, `ctgov`, `reporter`, `orphanet`, `omim`, `curated`, `analytics` |
| `provenance.source_record_id` | The specific record that asserts the relation | `VCV000012345`, `PMID:12345678`, `NCT01234567` |
| `provenance.url` | A link a human can open to check the evidence | `https://www.ncbi.nlm.nih.gov/clinvar/variation/12345/` |
| `provenance.retrieved_at` | When we fetched the record, as ISO 8601 UTC | `2026-10-03T14:00:00Z` |

Planned additions:
- `source_version` (release or date of the dump)
- `evidence_quote` (for extracted edges)
- `extractor` (`{model, prompt_version}` for LLM-derived edges)
- `supporting_edge_ids` (for computed edges)

## Evidence type

| `EvidenceType` | Definition | Examples | UI treatment (planned) |
|---|---|---|---|
| `observed` | Stated directly by a primary structured record that reports data | A ClinVar submission, a ClinicalTrials.gov record, a RePORTER grant | Solid edge |
| `curated` | Asserted by an expert-curated knowledge base, or by a human on the team with a cited source | HPO annotation, OMIM entry, Orphanet gene-disease, team curation | Solid edge with a curation badge |
| `inferred` | Produced by our pipeline: LLM extraction from text, or graph analytics | Extracted claim from an abstract, `shares_mechanism_with`, cluster membership | Dashed edge, labelled "hypothesis" |

The brief asks the atlas to *distinguish data from hypotheses and clinical proof*. Clinical proof, meaning an approved therapy or trial results, is marked on study and asset nodes through a status attribute. A link inferred from text is never presented as proof.

## Confidence rubric (planned)

`confidence` is a value in `[0, 1]` assigned by deterministic rules, not by the LLM's self-reported certainty. Compute a base value, apply the adjustments, then clamp the result to `[0.05, 0.99]`.

| Base | Condition |
|---|---|
| 0.90 | Curated knowledge base assertion (OMIM, Orphanet, HPO) or ClinVar with review status of expert panel or higher |
| 0.75 | ClinVar with multiple submitters and no conflicts; ClinicalTrials.gov or RePORTER record (the record itself is factual) |
| 0.60 | ClinVar with a single submitter; patient org verified on its own site |
| 0.50 | LLM-extracted claim with a verbatim quote from a peer-reviewed abstract |
| 0.30 | LLM-extracted claim from a preprint, or a hedged statement ("may", "suggests") |
| computed | Analytics edges: the similarity score times the minimum confidence of the supporting edges |

| Adjustment | Delta |
|---|---|
| Each additional independent source asserting the same relation | +0.05 (max +0.15) |
| Each contradicting edge | -0.15 |
| Reconcile match was `synonym` or `broader` rather than `exact` | -0.10 |
| Record older than 10 years with no newer support | -0.05 |

The rubric is versioned (`rubric_version` in the snapshot manifest). Changes to it go through a PR that updates this table.

## Contradictions

- When Extract finds a claim with `polarity=contradicts`, or two sources disagree (for example, ClinVar reports conflicting interpretations), both edges are kept. Each lists the other's id in `contradicted_by`.
- The UI shows contradictions next to the edge, never hidden behind it.
- Paths that pass through a contradicted edge are flagged, and Explain must say so.
- Counterexamples, such as the same gene with a different mechanism, are first-class. They are why a disease is **not** placed in a cluster.

## Honest gaps: the coverage report (planned)

When no supported route exists, or only weak ones (for example, all paths below confidence 0.4), the API returns a **coverage report** instead of a weak suggestion:

```json
{
  "query": "MONDO:...",
  "result": "no_supported_route",
  "searched": [
    {"source": "clinvar", "source_version": "2026-09", "records_found": 4},
    {"source": "hpo", "source_version": "2026-07", "records_found": 12},
    {"source": "pubmed", "query": "...", "records_found": 0},
    {"source": "ctgov", "records_found": 0}
  ],
  "not_searched": ["omim (no license)", "rareconnect (stretch)"],
  "missing_evidence": [
    "No mechanism annotation for the causal variant",
    "No patient organization found in NORD/Orphanet for this disease"
  ],
  "weak_leads": [{"path_edge_ids": ["e123", "e456"], "min_confidence": 0.3, "why_weak": "single preprint"}],
  "next_questions": [
    "Is the variant loss-of-function? A functional assay would place it in cluster X or Y."
  ]
}
```

This covers the brief's requirement: *"No supported route? Say so. Explain the search coverage and the missing evidence."*
