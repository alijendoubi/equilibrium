import { getAtlasClient } from "@/lib/api/client";
import type { Edge } from "@/lib/api/types";
import { NODE_TYPE_LABEL, formatConfidence, relationLabel } from "@/lib/format";
import { OG_CONTENT_TYPE, OG_SIZE, ogCard } from "@/lib/og/card";
import { decodeSegment } from "@/lib/params";

export const alt = "A disease in the Equilibrium atlas and its strongest sourced link";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

/** Reads in the edge's direction: "caused by GBA1" when the disease is the subject, otherwise
 * "ASPro-PD studies condition" (the other record is the subject). */
function describeLink(edge: Edge, nodeId: string, labels: Map<string, string>): string {
  const relation = relationLabel(edge.relation);
  const isSubject = edge.source_id === nodeId;
  const other = labels.get(isSubject ? edge.target_id : edge.source_id) ?? "a linked record";
  const claim = isSubject ? `${relation} ${other}` : `${other} ${relation}`;
  return `${claim} · ${edge.evidence_type} · confidence ${formatConfidence(edge.confidence)}`;
}

/** The disease, plus its strongest non-hypothesis link (edges come best first from the API). */
export default async function Image({ params }: { params: Promise<{ id: string }> }) {
  const id = decodeSegment((await params).id);
  const summary = id ? await getAtlasClient().getNode(id) : null;
  if (!summary) return ogCard({ eyebrow: "Rare disease atlas", title: "Not in the atlas yet" });

  const { node, edges, neighbors } = summary;
  const labels = new Map(neighbors.map((n) => [n.id, n.label]));
  const strongest = edges.find((e) => e.evidence_type !== "inferred");
  const detail = strongest
    ? describeLink(strongest, node.id, labels)
    : "No sourced links yet: an honest gap";
  return ogCard({ eyebrow: NODE_TYPE_LABEL[node.type], title: node.label, detail });
}
