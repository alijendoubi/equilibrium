import type { Metadata } from "next";
import { ProsePage } from "@/components/ProsePage";
import { REPO_URL } from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "Privacy · Equilibrium",
  description: "Equilibrium has no accounts, sets no cookies and stores no personal health data.",
};

export default function PrivacyPage() {
  return (
    <ProsePage title="Privacy" updated="2026-10-09">
      <p>
        Equilibrium is built to work without knowing who you are. There are no accounts, no sign-up
        and nothing to fill in.
      </p>

      <h2>What we do not collect</h2>
      <ul>
        <li>No accounts, names, email addresses or passwords.</li>
        <li>No cookies, local storage or tracking pixels, and no analytics.</li>
        <li>
          No personal health information. The atlas holds public research records about diseases,
          genes, studies and organisations, never about individual patients.
        </li>
      </ul>

      <h2>What reaches our servers</h2>
      <p>
        The website is hosted on Vercel and the data API on Render. Like any website, every request
        passes through their infrastructure, which records standard request logs: IP address,
        browser type, the page or API address requested and the time. What you type into search is
        part of that address, so it appears in these logs. We use the logs only to keep the service
        running and to stop abuse (for example rate limiting); we do not combine them with anything
        else or sell them. The hosts keep them according to their own policies.
      </p>

      <h2>AI providers</h2>
      <p>
        Search never sends what you type to an AI provider: semantic matches are looked up in
        vectors we computed in advance. Collaboration briefs are served from text generated in
        advance or from a cited template. If live AI briefs are switched on, the request sent to
        OpenAI contains only the public research records on the selected path, never your search
        text or anything about you.
      </p>

      <h2>Public research data</h2>
      <p>
        Named investigators appear only as public professional information from publications and
        grant records (name, affiliation, source link). To ask for a correction, open an issue on{" "}
        <a href={`${REPO_URL}/issues`}>GitHub</a>.
      </p>

      <h2>Contact and changes</h2>
      <p>
        For anything sensitive, use GitHub&apos;s private reporting on the{" "}
        <a href={`${REPO_URL}/security`}>security page</a>. If this policy changes, the date above
        changes with it, and the history is public in the repository.
      </p>
    </ProsePage>
  );
}
