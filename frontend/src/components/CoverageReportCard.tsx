import type { CoverageReport } from "@/lib/api/types";
import { formatConfidence } from "@/lib/format";

const RESULT_LABEL: Record<CoverageReport["result"], string> = {
  supported: "Supported routes found",
  weak_routes_only: "Only weak routes found",
  no_supported_route: "No supported route",
};

/** The honest gap: what we searched, what is missing, and the next question. */
export function CoverageReportCard({
  report,
  headingLevel = 4,
}: {
  report: CoverageReport;
  /** Level of the section headings, one below the heading the card sits under. */
  headingLevel?: 3 | 4;
}) {
  const Heading = headingLevel === 3 ? "h3" : "h4";
  return (
    <section
      aria-label="Coverage report"
      className="rounded-xl border border-dashed border-border p-4 text-sm"
    >
      <p className="font-semibold">{RESULT_LABEL[report.result]}. Here is what we checked.</p>

      <Heading className="mt-3 text-xs font-semibold tracking-wider text-muted uppercase">
        Searched
      </Heading>
      <ul className="mt-1 space-y-1">
        {report.searched.map((s) => (
          <li key={`${s.source}-${s.query ?? ""}`}>
            <span className="font-medium">{s.source}</span>
            {s.query && <span className="text-muted"> ({s.query})</span>}: {s.records_found}{" "}
            {s.records_found === 1 ? "record" : "records"}
            {s.source_version && <span className="text-muted"> · version {s.source_version}</span>}
          </li>
        ))}
      </ul>
      {report.not_searched.length > 0 && (
        <p className="mt-2 text-muted">Not searched: {report.not_searched.join(", ")}.</p>
      )}

      {report.missing_evidence.length > 0 && (
        <>
          <Heading className="mt-3 text-xs font-semibold tracking-wider text-muted uppercase">
            Missing
          </Heading>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {report.missing_evidence.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </>
      )}

      {report.weak_leads.length > 0 && (
        <>
          <Heading className="mt-3 text-xs font-semibold tracking-wider text-muted uppercase">
            Weak leads
          </Heading>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {report.weak_leads.map((l) => (
              <li key={l.path_edge_ids.join("-")}>
                {l.why_weak} (lowest confidence {formatConfidence(l.min_confidence)})
              </li>
            ))}
          </ul>
        </>
      )}

      {report.next_questions.length > 0 && (
        <>
          <Heading className="mt-3 text-xs font-semibold tracking-wider text-muted uppercase">
            Next questions
          </Heading>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {report.next_questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
