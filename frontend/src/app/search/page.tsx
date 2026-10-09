import type { Metadata } from "next";
import Link from "next/link";
import { MatchReasonBadge, TypeBadge } from "@/components/Badges";
import { DataNotice } from "@/components/MockBanner";
import { PageHeader } from "@/components/PageHeader";
import { getServerAtlasClient } from "@/lib/api/server-client";
import { displayId, nodeHref } from "@/lib/format";
import { firstParam } from "@/lib/params";

export const metadata: Metadata = { title: "Search · Equilibrium" };

interface SearchPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/** True when two names differ only in case or surrounding space (no need to repeat the match). */
function sameText(a: string, b: string): boolean {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const q = firstParam((await searchParams).q).trim();
  const client = await getServerAtlasClient();
  const response = q ? await client.search(q) : null;

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <PageHeader query={q} />
      <DataNotice isMock={client.isMock} usedFallback={client.usedFallback} />

      <h1 className="mt-8 text-2xl font-semibold tracking-tight">
        {q ? (
          <>
            Results for <span className="text-cluster">&ldquo;{q}&rdquo;</span>
          </>
        ) : (
          "Search the atlas"
        )}
      </h1>

      {!response && (
        <p className="mt-4 text-muted">Type a disease, gene or symptom in the search box above.</p>
      )}

      {response && response.results.length === 0 && (
        <section aria-labelledby="no-match" className="mt-6 rounded-2xl border border-border p-6">
          <h2 id="no-match" className="font-semibold">
            No match.
          </h2>
          <p className="mt-2 text-sm text-muted">
            We searched: {response.searched.join(", ")}. Nothing matched &ldquo;{q}&rdquo;. Try
            another name or a gene symbol. If this disease is missing, that gap is worth knowing.
          </p>
        </section>
      )}

      {response && response.results.length > 0 && (
        <>
          <p className="mt-2 text-sm text-muted" aria-live="polite">
            {response.results.length} {response.results.length === 1 ? "match" : "matches"}.
            Searched: {response.searched.join(", ")}.
          </p>
          <ol aria-label="Search results" className="mt-6 space-y-3">
            {response.results.map((r) => (
              <li key={r.node.id}>
                <Link
                  href={nodeHref(r.node.id)}
                  className="block rounded-2xl border border-border bg-surface p-4 hover:border-cluster"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <TypeBadge type={r.node.type} />
                    <MatchReasonBadge reason={r.match_reason} />
                    <span className="text-xs text-muted">{displayId(r.node.id)}</span>
                  </div>
                  <p className="mt-2 font-semibold">{r.node.label}</p>
                  {r.match_reason !== "exact" && !sameText(r.matched_text, r.node.label) && (
                    <p className="mt-1 text-sm text-muted">
                      Matched {r.match_reason === "synonym" ? "synonym" : "on"}:{" "}
                      <span className="text-foreground">&ldquo;{r.matched_text}&rdquo;</span>
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ol>
        </>
      )}
    </main>
  );
}
