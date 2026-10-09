# Demo Script

> **Historical document.** Written for the Hack-Nation submission (October 2026) and kept for the record; it is not maintained. Code comments cite its section numbers. For the current project see the [README](../README.md) and [ARCHITECTURE](ARCHITECTURE.md).

Status: **ready to record**. Every step below exists in the build (checked end to end against the live API on 2026-10-04). Record on the deployed URL; if the backend is unreachable, the UI falls back to bundled demo data and shows "Showing cached demo data", so do a warm-up first.

The brief requires: *"A Team video and a 1-minute walkthrough. Follow a family or patient group through the graph to either a justified collaboration and next step, or an honest gap with a plan to investigate it."* We show both.

## 1-minute walkthrough (following Maria)

Maria leads a family group for **neuronopathic Gaucher disease (types 2 and 3)**. There is no approved therapy for the neurological disease: enzyme replacement does not cross the blood-brain barrier.

| Time | Click path (deployed URL) | Narration | What is on screen |
|---|---|---|---|
| 0:00-0:06 | Home page | "Maria's child has neuronopathic Gaucher disease. There is no treatment for the brain disease. She knows the gene, GBA1, and not much else." | One search box, example chips, Maria's three questions |
| 0:06-0:12 | Click the chip **Gaucher disease**, then open **Gaucher disease type II** | "One search. Names and synonyms resolve to one stable disease." | Results with match reason (exact / synonym), `MONDO:0009266` |
| 0:12-0:24 | Disease page, then **Explore connection** to the ASPro-PD path (`/path?from=MONDO%3A0009266&to=clinicaltrials%3ANCT05778617`). Click the GBA1 to Parkinson's edge | "Her disease is caused by GBA1. Carrying one faulty GBA1 copy is a major risk factor for Parkinson's. A different name, the same gene and the same lysosomal biology. Every link shows its source." | Chain Gaucher type II, GBA1, late-onset Parkinson disease, ASPro-PD. Evidence panel: source (OMIM / Orphanet), record id, date, confidence and reasons |
| 0:24-0:40 | **What to do next** (action view `/actions/MONDO%3A0009266`) | "The Parkinson's community already runs ASPro-PD, a phase 3 ambroxol trial with 330 people, funded by Cure Parkinson's. The atlas shows what is reusable, and what differs: Parkinson's patients aged 35 to 75 on a fixed 1260 mg/day dose, versus a five-patient Gaucher pilot at 25 mg/kg/day." | Partner Cure Parkinson's with why and cited edges; ASPro-PD with "Reusable" and "What differs"; next experiment marked hypothesis |
| 0:40-0:52 | **Draft collaboration brief** on ASPro-PD | "OpenAI drafts a collaboration brief. Every sentence cites the evidence behind it, and it says what an expert must check first." | Steps with edge-id chips, summary, caveats, "AI-generated (gpt-6.1-sol)" badge |
| 0:52-1:00 | Search **Saposin C deficiency**, open it | "And when there is no supported route, the atlas says so: no trials, no patient group, and the next question to test." | Gap card: sources searched, what is missing, closest communities (International Gaucher Alliance), "Help build the missing community" |

Narration total is about 150 words. Keep it calm; let the screen carry the detail.

### Before recording

- [ ] OpenAI caches precomputed and deployed (README "Built with OpenAI"), so the brief shows **AI-generated**, not "Template (AI unavailable)". If the key is unavailable, say "drafted from the evidence" and do not claim AI on screen.
- [ ] Backend warmed: open `https://<render-service>.onrender.com/health` and check `"snapshot":"loaded"`.
- [ ] No "Showing cached demo data" notice on screen (that means the backend was not reached).
- [ ] Recorded on the deployed URL, 1080p, readable zoom, no keys, tokens or personal tabs visible.
- [ ] Captions or burned-in subtitles.
- [ ] Do not use `gaucherregistry.com` anywhere: on 2026-10-03 it served an online casino.

## Team video outline (2-3 minutes)

1. **Who we are** (15 s): Team Equilibrium: Ali Jendoubi (lead, full stack and AI), Khaled Md Saifullah (data), Clara Hajj (story and narration).
2. **The problem** (20 s): about 10,000 rare diseases, fewer than 5% with an approved treatment. Knowledge is scattered; names hide mechanisms; groups rebuild what already exists.
3. **Our angle** (25 s): we chose the GBA1/GCase–lysosomal dysfunction cluster. Neuronopathic Gaucher has a real neurological treatment gap; GBA1 links it to Parkinson's, which has a far larger research ecosystem. We do not claim to discover that known link; we use it as a **validated anchor**, then search the same gene–pathway–phenotype neighbourhood for less obvious diseases, assets and evidence gaps.
4. **How it works** (35 s): sources (Monarch for MONDO/HPO/OMIM-sourced links, GO, ClinVar, ClinicalTrials.gov, curated patient organisations) become an evidence graph where every edge has a source, date, confidence and evidence type. **Built with OpenAI:** embeddings plus `gpt-6-luna` resolve names to one node; `gpt-6.1-sol` writes the collaboration brief, and a validator rejects any sentence that does not cite an edge. Everything is cached, so the demo never depends on a live call.
5. **Demo** (40 s): condensed walkthrough.
6. **10x** (25 s): the table below.
7. **What is next** (15 s): expert review of the brief, PubMed claim extraction at scale, patient-contributed evidence.

## 10x moonshot

**Milestone:** a neuronopathic Gaucher family group launches a research collaboration that reuses Parkinson's (GBA1-PD) trial infrastructure: ambroxol safety data from ASPro-PD, a GBA1-stratified design, and a shared biomarker protocol (glucosylsphingosine).

The realistic framing: **10x applies to the early find-mechanism, asset and partner step.** It does not apply to curing anything, or to regulatory timelines.

| Step | Status quo for a small rare community | Equilibrium route | What makes it faster |
|---|---|---|---|
| Find the shared mechanism and the larger community | Months of conferences, cold emails and reading | Minutes: cited path Gaucher, GBA1, Parkinson's | Mechanism-first graph with sources on every edge |
| Find reusable assets | Scattered across registries, papers and press releases | Same session: ASPro-PD, the ambroxol registry spanning both communities, PR001 gene therapy tested in both | Assets mapped onto the shared gene |
| Find partners | Personal networks | Cure Parkinson's, MJFF GBA1-PD programme, International Gaucher Alliance, each with the evidence for why | Partners reached through cited edges |
| First collaboration brief | Weeks of expert time | A sourced draft for expert review, with population, dose and endpoints already compared | OpenAI brief constrained to cited edges |
| **Total for this step** | **about 6-12 months (team estimate)** | **about 2-4 weeks including expert review (team estimate)** | **about 10x** |

**Assumptions (state them on screen):**
1. Parkinson's sponsors and funders are willing to share protocols, safety data or biomarker methods with a rare-disease group.
2. Parkinson's evidence does not transfer automatically to neuronopathic Gaucher: population, age, dose (weight-based in nGD, fixed in PD), severity and endpoints differ. Venglustat is the reminder: positive in Gaucher type 3, no benefit in GBA-Parkinson's.
3. "No approved therapy for the neurological disease" is true as of 2026-10-04; venglustat for Gaucher type 3 is under FDA review (decision expected 2026-11-25, from press coverage).
4. Status-quo durations are team estimates, not measured.

**What must be validated next:**
- One expert check of the brief: a Gaucher clinician and a Parkinson's trialist.
- Whether ASPro-PD collects GCase activity or glucosylsphingosine data.
- One contact with the International Gaucher Alliance about family interest.
