import type { Metadata } from "next";
import { ProsePage } from "@/components/ProsePage";
import { REPO_URL } from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "Medical disclaimer · Equilibrium",
  description: "Equilibrium is a research tool. It is not medical advice.",
};

export default function DisclaimerPage() {
  return (
    <ProsePage title="Medical disclaimer" updated="2026-10-09">
      <p className="rounded-xl border border-contradiction px-4 py-3 font-medium">
        Equilibrium is for research context only. It is not medical advice, and it must not be used
        to diagnose, treat or make decisions about any person&apos;s care.
      </p>

      <h2>What the atlas is</h2>
      <p>
        The atlas organises published and public research records so that communities can find
        related work and ask better questions. It shows what sources say, how confident we are and
        where evidence is missing. It does not recommend treatments, doses, trials or clinicians.
      </p>

      <h2>Limits you should know</h2>
      <ul>
        <li>
          Sources can be incomplete, out of date or wrong, and our processing can introduce errors.
          Every link shows its source and retrieval date so you can check it.
        </li>
        <li>Dashed links are hypotheses produced by our pipeline, not findings.</li>
        <li>
          Doses and outcomes appear only as published research facts to compare, never as
          recommendations.
        </li>
        <li>
          AI-written summaries are labelled and cite the links they describe, but they can still be
          wrong. A cited template is used when no AI text is available.
        </li>
        <li>
          An honest gap means our sources had no supported route. It does not mean that no relevant
          work exists.
        </li>
      </ul>

      <h2>Talk to a professional</h2>
      <p>
        For any question about a diagnosis, treatment or trial, talk to a qualified healthcare
        professional or the trial&apos;s study team. In an emergency, contact your local emergency
        services.
      </p>

      <h2>Found a mistake?</h2>
      <p>
        Please report it on <a href={`${REPO_URL}/issues`}>GitHub</a> with the link or page
        concerned. Do not include personal health information in a report.
      </p>
    </ProsePage>
  );
}
