import type { Edge } from "@/lib/api/types";
import { formatDate, relationLabel } from "@/lib/format";

/** GitHub issue form for edge reports (.github/ISSUE_TEMPLATE/edge-report.yml, contract on #95). */
export const REPORT_FORM_URL = "https://github.com/alijendoubi/equilibrium/issues/new";
export const REPORT_TEMPLATE = "edge-report.yml";
/** Keep prefill well under the ~8 kB URL limit browsers and GitHub accept. */
const MAX_FIELD_LENGTH = 1500;

const clip = (value: string) =>
  value.length > MAX_FIELD_LENGTH ? `${value.slice(0, MAX_FIELD_LENGTH - 1)}…` : value;

/**
 * A prefilled "report a problem" link for one edge. The query keys are the form's field ids.
 * Only public data goes in: the edge, its provenance and the page; the reporter writes the rest.
 */
export function edgeReportUrl(edge: Edge, labelOf: (id: string) => string, page?: string): string {
  const p = edge.provenance;
  const claim = `${labelOf(edge.source_id)} ${relationLabel(edge.relation)} ${labelOf(edge.target_id)}`;
  const sources = [
    p.source,
    p.source_record_id,
    p.url ?? "no url",
    formatDate(p.retrieved_at),
  ].join(" · ");
  const params = new URLSearchParams({
    template: REPORT_TEMPLATE,
    title: clip(`data: problem with edge ${edge.id}`),
    edge_id: edge.id,
    claim: clip(claim),
    sources: clip(sources),
  });
  if (page) params.set("page", clip(page));
  return `${REPORT_FORM_URL}?${params.toString()}`;
}
