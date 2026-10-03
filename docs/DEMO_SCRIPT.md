# Demo Script

Status: **skeleton**. Fill in the bracketed placeholders with real nodes, edges and screens from the deployed build. Never show a step the product cannot actually do. If a step is not ready, cut it or present it explicitly as planned.

The brief requires: *"A Team video and a 1-minute walkthrough. Follow a family or patient group through the graph to either a justified collaboration and next step, or an honest gap with a plan to investigate it."*

## 1-minute walkthrough (following Maria)

Target: 60 seconds. The timings below add up to 60 s. Narration is short; let the screen do the work.

| Time | Screen | Narration (draft) | Evidence shown |
|---|---|---|---|
| 0:00-0:07 | Landing page, one search box | "Maria leads a patient group for [DISEASE X]. There is no approved treatment. She knows the gene, [GENE A], and not much else." | none |
| 0:07-0:15 | Types the disease. Synonym resolution shows the MONDO ID | "One search. The atlas resolves the name to a stable disease identity." | `MONDO:[...]`, synonyms |
| 0:15-0:25 | Disease -> mechanism -> [GENE B] -> [DISEASE Y] path. Edge panel open | "Her variant is [loss of function] in [PATHWAY]. [GENE B] breaks the same pathway in [DISEASE Y]. A different name, the same problem." | Edge source, confidence, observed vs inferred badge, any contradiction |
| 0:25-0:35 | Cluster view: Maria's disease sits next to [DISEASE Y]. Counterexample visible | "They cluster on mechanism and phenotype, not on name. And here is a disease with the same gene but a different mechanism. The atlas keeps it apart." | Top shared HPO terms, mechanism edge |
| 0:35-0:45 | Patient action view: [PATIENT GROUP Y], [REGISTRY / NATURAL HISTORY STUDY NCT...] | "[GROUP Y] already runs a registry and a natural history study. Here is what is reusable, and what differs: [ELIGIBILITY / BIOMARKER]." | `operates`, `studies_condition` edges |
| 0:45-0:55 | Explain panel: plain-language proposal, each sentence citing edge ids | "Equilibrium drafts a sourced proposal to [GROUP Y] and names what an expert must check first." | Edge-id citations |
| 0:55-1:00 | Honest-gap card for a sparse disease (optional cut) | "And when there is no supported route, it says so, and shows what to test next." | Coverage report |

### Fallback: the honest-gap ending

If the demo cluster has no strong supported route, end on the gap instead:
- the coverage report (sources searched, records found)
- the missing evidence
- the single next question, for example "Is the variant loss-of-function? A functional assay decides which cluster applies."

### Recording checklist

- [ ] Recorded on the deployed URL, not localhost
- [ ] Backend warmed up beforehand, so there are no cold starts
- [ ] Resolution 1080p, browser zoom at a level where text is readable
- [ ] No API keys, tokens or personal tabs visible
- [ ] Captions or burned-in subtitles

## Team video outline (2-3 minutes)

1. **Who we are** (15 s): Team Equilibrium, names and roles.
2. **The problem** (20 s): 10,000 rare diseases, fewer than 5% treated. Names hide mechanisms. Groups rebuild what already exists.
3. **Our insight** (20 s): organize by mechanism and phenotype. Every edge carries evidence. Gaps are reported honestly.
4. **How it works** (40 s): the architecture diagram. Sources, then OpenAI Extract and Reconcile, then the evidence graph, clustering and Explain, then the UI. Explain why evidence-first matters.
5. **Demo** (40 s): a condensed version of the walkthrough.
6. **10x moonshot** (25 s): the table below.
7. **What is next and what needs validation** (20 s): more sources, patient-contributed evidence, expert review loop.

## 10x moonshot (template)

Pick **one** meaningful milestone, as the brief asks. Suggested milestone: **launching a shared natural history study across two patient communities that share a mechanism.**

Every number in the "existing timeline" column must come from a cited source, or be labelled as an estimate with its reasoning. Do not invent figures.

| Step toward the milestone | Existing route (time, source) | Equilibrium route (time) | What makes it faster | Assumption to validate |
|---|---|---|---|---|
| Discover that another community shares the mechanism | [e.g. X months to years, often by chance at conferences; cite or estimate] | [minutes: search + cluster view] | Mechanism-based clustering across names | Clusters are biologically valid (expert review) |
| Find an existing registry or natural history study | [X months; cite/estimate] | [minutes: action view] | Assets mapped onto the cluster | Asset metadata is current and accessible |
| Judge whether the asset or design is reusable | [X months; cite/estimate] | [days: sourced diff of eligibility and endpoints + expert review] | Explain lists what differs and what needs expert review | Differences can be resolved through protocol amendment |
| Identify a shared investigator or funder | [X months; cite/estimate] | [minutes: network overlap] | Investigator and funder bridges | Contact data is public and current |
| Agree a joint protocol and launch | [X years; cite/estimate] | [X months] | Reused registry and design instead of building from scratch | Governance and consent can be shared |
| **Total** | **[X years]** | **[Y months]** | | **Ratio: [X/Y]** |

**Biggest assumptions:**
- [list them]

**What would need to be validated next:**
- [list it]
