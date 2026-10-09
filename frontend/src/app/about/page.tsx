import type { Metadata } from "next";
import Link from "next/link";
import { ProsePage } from "@/components/ProsePage";
import { REPO_URL } from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "About · Equilibrium",
  description: "What Equilibrium is, who it is for, and how it decides what to show.",
};

export default function AboutPage() {
  return (
    <ProsePage title="About Equilibrium" updated="2026-10-09">
      <p>
        Equilibrium is an open-source, evidence-first atlas of rare diseases. It helps patient-group
        leaders, researchers and funders see where diseases connect through shared genes,
        mechanisms, studies, organisations and research assets, and what those connections make
        possible.
      </p>

      <h2>How it decides what to show</h2>
      <ul>
        <li>
          <strong>Every line is a sourced claim.</strong> Each link carries its source, record, URL,
          retrieval date, evidence type and a confidence score with reasons.
        </li>
        <li>
          <strong>Hypotheses look different.</strong> Links inferred by our pipeline are drawn
          dashed, labelled as hypotheses and always rank below curated evidence.
        </li>
        <li>
          <strong>Disagreement is visible.</strong> Contradicting records are drawn in red, not
          hidden.
        </li>
        <li>
          <strong>No answer is an answer.</strong> When no supported route exists, the atlas says
          what it searched and what is missing (an honest gap).
        </li>
        <li>
          <strong>AI is labelled.</strong> Text written by a model carries an
          &ldquo;AI-generated&rdquo; badge and must cite the links it describes.
        </li>
      </ul>

      <h2>Coverage today</h2>
      <p>
        The atlas currently covers one slice in depth: GBA1/GCase–lysosomal dysfunction, from
        Gaucher disease to GBA1-related Parkinson&apos;s disease. More disease clusters are planned.
        Data comes from public sources including the Monarch Initiative, Orphanet, OMIM (via
        Monarch), the Human Phenotype Ontology, the Gene Ontology, ClinVar, PubMed,
        ClinicalTrials.gov and NIH RePORTER, plus curated patient organisations.
      </p>

      <h2>Open source</h2>
      <p>
        The code is MIT-licensed and developed in the open on <a href={REPO_URL}>GitHub</a>, where
        you can read how every score is computed and report problems. Equilibrium began at
        Hack-Nation&apos;s 7th Global AI Hackathon in October 2026.
      </p>
      <p>
        Equilibrium is a research tool, not medical advice. Read the{" "}
        <Link href="/disclaimer">medical disclaimer</Link>.
      </p>
    </ProsePage>
  );
}
