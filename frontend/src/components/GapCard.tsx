import { CoverageReportCard } from "@/components/CoverageReportCard";
import type { CoverageReport } from "@/lib/api/types";
import type { Community } from "@/lib/gap";

interface GapCardProps {
  diseaseLabel: string;
  report: CoverageReport;
  communities: Community[];
}

/** The honest "no supported route" answer, shown first, with the closest communities and a next step. */
export function GapCard({ diseaseLabel, report, communities }: GapCardProps) {
  const first = communities[0];
  return (
    <section
      aria-labelledby="gap-heading"
      className="rounded-2xl border-2 border-dashed border-action bg-surface p-5"
    >
      <p className="text-xs font-semibold tracking-wider text-action uppercase">Honest gap</p>
      <h2 id="gap-heading" className="mt-1 text-xl font-semibold">
        No community found yet for {diseaseLabel}
      </h2>
      <p className="mt-2 text-sm text-muted">
        We did not find a patient group, study or shared mechanism with enough evidence to
        recommend. Here is exactly what we checked, what is missing and the next question to ask.
      </p>

      <div className="mt-4">
        <CoverageReportCard report={report} />
      </div>

      {communities.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold tracking-wider text-muted uppercase">
            Closest communities
          </h3>
          <ul className="mt-2 space-y-2 text-sm">
            {communities.map((c) => (
              <li key={c.id}>
                <a
                  href={c.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-cluster underline-offset-4 hover:underline"
                >
                  {c.label}
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
                <span className="text-muted"> · {c.why}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5 rounded-xl bg-background p-4">
        <p className="font-semibold">Help build the missing community</p>
        <p className="mt-1 text-sm text-muted">
          {first
            ? `Families with ${diseaseLabel} have no dedicated group yet. Contact ${first.label} and ask whether they can welcome them, or help start one.`
            : `Families with ${diseaseLabel} have no dedicated group yet. Share this gap with your clinical team or a rare disease alliance.`}
        </p>
        {first && (
          <a
            href={first.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-block rounded-xl border border-action px-3 py-1.5 text-sm font-medium text-action hover:bg-surface"
          >
            Contact {first.label}
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        )}
      </div>
    </section>
  );
}
