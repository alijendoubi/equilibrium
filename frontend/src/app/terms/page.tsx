import type { Metadata } from "next";
import Link from "next/link";
import { ProsePage } from "@/components/ProsePage";
import { REPO_URL } from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "Terms of use · Equilibrium",
  description: "How you may use Equilibrium, its code and its data.",
};

export default function TermsPage() {
  return (
    <ProsePage title="Terms of use" updated="2026-10-09">
      <p>By using Equilibrium you agree to these terms. They are short on purpose.</p>

      <h2>Research use, not medical advice</h2>
      <p>
        Equilibrium is provided for research context only. Read the{" "}
        <Link href="/disclaimer">medical disclaimer</Link>; it is part of these terms.
      </p>

      <h2>Code and data</h2>
      <ul>
        <li>
          The source code is open source under the{" "}
          <a href={`${REPO_URL}/blob/main/LICENSE`}>MIT licence</a>.
        </li>
        <li>
          The data comes from third-party sources and stays under their own terms. Each link shows
          its source; the full list and licences are in{" "}
          <a href={`${REPO_URL}/blob/main/docs/DATA_SOURCES.md`}>DATA_SOURCES</a>. If you reuse
          data, follow the source&apos;s terms and attribute it.
        </li>
      </ul>

      <h2>Fair use of the service</h2>
      <ul>
        <li>
          Do not try to disrupt the service, bypass rate limits or access it in ways it was not
          built for.
        </li>
        <li>
          For bulk access, run your own copy from the repository instead of scraping the public
          site.
        </li>
        <li>We may limit or block traffic that harms the service for others.</li>
      </ul>

      <h2>No warranty</h2>
      <p>
        Equilibrium is provided &ldquo;as is&rdquo;, without warranty of any kind. To the extent the
        law allows, the maintainers are not liable for any loss arising from its use. The service
        may change, pause or stop at any time.
      </p>

      <h2>Changes</h2>
      <p>
        If these terms change, the date above changes with them, and the history is public in the{" "}
        <a href={REPO_URL}>repository</a>.
      </p>
    </ProsePage>
  );
}
