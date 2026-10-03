# ADR 0003: Demo cluster is GBA1/GCase–lysosomal dysfunction (Gaucher / GBA1 -> Parkinson's)

- **Status:** Accepted
- **Date:** 2026-10-03
- **Deciders:** Team Equilibrium (task A1, issue #14)

## Context

The brief asks for one focused slice with enough biology, research and patient-group data to show a complete path, plus an honest gap. [PROJECT_PLAN.md](../PROJECT_PLAN.md) first recommended presynaptic SNAREopathies (VAMP2 hero, STXBP1 partner, CPLX1 gap). We compared that against a lysosomal cluster centred on GBA1.

The GBA1 neighbourhood has a property no other candidate has: **one gene links an ultra-rare paediatric disease to a common adult disease**, and research money and trial infrastructure have flowed to the common one. That is exactly the "who shares our disease characteristics, what already exists" question Maria asks. All facts below were checked live on 2026-10-03; see the seed list in [DATA_SOURCES.md](../DATA_SOURCES.md#demo-cluster-gaucher--gba1---parkinsons).

- Two faulty GBA1 copies cause Gaucher disease (Monarch `causes`, OMIM-sourced, types 1, 2, 3 and perinatal lethal). One faulty copy is a Parkinson's risk factor: Monarch `contributes_to` late-onset Parkinson disease (MONDO:0008199, OMIM:168600).
- In the 16-centre study by Sidransky et al. (NEJM 2009, PMID 19846850), N370S or L444P was found in 15% of Ashkenazi Jewish PD patients vs 3% of non-Ashkenazi patients. Full sequencing raised the non-Ashkenazi figure to 7%.
- Neuronopathic Gaucher disease (types 2 and 3) has no approved therapy for its neurological disease. Enzyme replacement does not cross the blood-brain barrier. Sanofi's February 2026 release states "there are no approved treatments for neurologic manifestations of GD3".
- PD-side assets are reusable: ASPro-PD (NCT05778617, phase 3, ambroxol, 330 participants, about half GBA1 carriers, recruiting). The same gene therapy (LY3884961 / PR001) is in trials for GBA1-PD (NCT04127578) and for type 2 Gaucher (NCT04411654). An ambroxol registry already covers both populations (NCT04388969).

## Decision

**Rationale:** We chose the GBA1/GCase–lysosomal dysfunction cluster for three reasons. Neuronopathic Gaucher has a real neurological treatment gap. GBA1/GCase gives a biologically strong link to Parkinson's. And Parkinson's acts as our validated anchor. We are not claiming to discover that known link. We use it to validate the system, then search the same gene-pathway-phenotype neighbourhood for less obvious diseases, assets, researchers and evidence gaps.

1. The demo cluster is **GBA1/GCase–lysosomal dysfunction** (Gaucher / GBA1 -> Parkinson's), with lysosomal neighbours:
   - PSAP (saposin C deficiency)
   - SCARB2 (action myoclonus-renal failure)
   - SMPD1 (Niemann-Pick A/B)
   - ATP13A2 (Kufor-Rakeb)
   - CTSD (CLN10)
   - GBA2 (SPG46)
2. **Hero:** neuronopathic Gaucher disease, types 2 and 3 (MONDO:0009266, MONDO:0009267). **Partner disease:** GBA1-associated Parkinson's (MONDO:0008199).
3. **Validated anchor:** GBA1 -> GCase / lysosomal glycosphingolipid degradation -> PD risk. This uses curated Monarch/OMIM edges and the ambroxol evidence (Narita et al. 2016, PMC4774255; ASPro-PD).
4. **Hypotheses:** neighbour links that are not curated gene-disease associations are shown dashed and labelled "hypothesis". Examples: SMPD1 and PD risk, the contested PSAP and PD susceptibility link, and SCARB2 GCase trafficking as a shared mechanism.
5. **Counterexample:** venglustat. MOVES-PD (NCT02906020) in GBA1-PD was terminated after missing its primary and secondary endpoints (Giladi et al. 2023, PMID 37479372). LEAP2MONO (NCT05222906) in Gaucher type 3 met its primary endpoints (Sanofi, 2026-02-02). Same gene and same drug, but different populations and outcomes, so a shared mechanism does not mean shared results.
6. **Honest gap:** Gaucher disease due to saposin C deficiency (MONDO:0012517). Evidence for the gap:
   - 0 condition-matched trials
   - 0 NIH RePORTER projects
   - no dedicated patient organization found
   - "no specific therapy is approved" (PMID 41812503)
7. SNAREopathies are kept as the documented alternative. PROJECT_PLAN section 4 keeps their verified seed data.

## Consequences

**Positive**
- The story is easy to grasp in a 1-minute video: a rare childhood disease and a common adult disease share one gene, and the common disease has trials.
- Real, checkable assets exist on both sides, including two that already span both populations (the ambroxol registry, and PR001 in two trials).
- The counterexample is genuine and well documented, which helps on the Graph quality criterion.
- The data is rich: 50-92 HPO annotations per Gaucher entry, OMIM- and Orphanet-sourced gene-disease edges in Monarch, and 179 ClinicalTrials.gov records for "Gaucher".

**Negative / risks**
- **"No approved therapy" may expire during judging.** The FDA set a target action date of 2026-11-25 for venglustat in GD3 (priority review, as reported in May 2026). The UI must say "as of 2026-10-03" and show the pending NDA, not a timeless claim.
- Gaucher type 1 has approved ERT and SRT, so the demo must focus on the neurological disease (types 2 and 3) to keep the unmet-need framing honest.
- Population numbers depend on ancestry and on the screening method (15% vs 3%, and 7% with full sequencing). Show them with their source and caveats.
- Dosing comparisons (nGD weight-based vs PD fixed dose) are research evidence and must never be presented as treatment advice.
- PD literature is huge, so the Extract corpus must be filtered to GBA1/GCase abstracts.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Presynaptic SNAREopathies (VAMP2 hero, STXBP1 partner, CPLX1 gap) | Strong mechanism story and a real multi-gene natural history study (NCT06555965). But the 10x route depends on one sponsor adding a gene, the hero's mechanism is unconfirmed, and there is no rare-to-common bridge. Kept as the fallback in PROJECT_PLAN section 4. |
| Neuronal ceroid lipofuscinoses (CLN3 hero) | Rich registries. But CLN2 has an approved therapy, which muddies the story, and there is no common-disease bridge. CLN10 (CTSD) is still included as a lysosomal neighbour. |
| Congenital disorders of glycosylation | Shared pathway, many untreated members. Smaller literature per disease and fewer reusable assets. |
| Channelopathy DEE (SCN2A, KCNQ2) | Best "same gene, gain vs loss of function" story. But mechanism labels need expert sourcing, and there is no common-disease bridge. |
