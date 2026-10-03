# ADR 0002: Evidence-first graph

- **Status:** Accepted
- **Date:** 2026-10-03
- **Deciders:** Team Equilibrium

## Context

The brief's bar is that "every edge has an explanation and a source". It also asks the atlas to:
- distinguish observations from inferred links
- surface contradictory findings
- say so when there is no supported route

Two judging criteria are directly about this: **Graph quality**, which covers counterexamples and uncertainty, and **Evidence integrity**, which covers sourced, cross-checked claims that distinguish data from hypotheses.

LLM extraction and graph analytics will both produce plausible but unsupported links. If those links look the same as curated facts, the atlas could mislead a family.

## Decision

1. **The edge is the unit of evidence.** An edge cannot be created without:
   - `provenance` (`source`, `source_record_id`, `url`, `retrieved_at`)
   - `confidence` (from 0 to 1, assigned by a rule-based rubric)
   - `evidence_type` (`observed`, `curated` or `inferred`)
   - `contradicted_by`

   The Pydantic model enforces this.
2. **Multiple edges per relation.** We use a multigraph, so independent sources asserting the same relation stay separate. Agreement raises confidence, and disagreement stays visible.
3. **LLM output is always `inferred`.** It must carry a verbatim quote found in the source. Reconcile may only choose IDs from the candidate lists it is given.
4. **Explanations cite edges.** Every sentence produced by Explain references edge ids on the path. Uncited text is rejected.
5. **Gaps are a result, not an error.** When no route meets the support threshold, the API returns a coverage report listing:
   - sources searched
   - missing evidence
   - weak leads, with reasons
   - next questions
6. **Computed edges are traceable.** Similarity, cluster and bridge edges list the supporting edge ids that justify them.

See [EVIDENCE_MODEL.md](../EVIDENCE_MODEL.md) for the full contract.

## Consequences

**Positive**
- Every claim in the UI can be checked with one click, which builds trust with families and scientists alike.
- Directly addresses two judging criteria and the honest-gap requirement.
- Data quality problems surface as low confidence or contradictions instead of silent errors.

**Negative**
- More work per connector, because provenance must be mapped for every record.
- The graph has fewer edges than an "extract everything" approach, and some true links will be missing until evidence is added.
- The confidence rubric is hand-tuned and will need calibration later.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Let the LLM answer directly over retrieved documents (RAG chat) | Fast to build, but claims are not graph edges. That means no clustering, no stable IDs, and weak traceability. |
| Use the LLM's self-reported confidence | It is not calibrated, and it cannot be reproduced or audited |
| Store provenance only per source (for example, "from ClinVar") | Not checkable. The brief needs record-level citations. |
| Drop contradicted edges | Hides uncertainty. The brief explicitly asks to surface contradictory findings. |
