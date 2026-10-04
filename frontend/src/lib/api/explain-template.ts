import { displayId, formatConfidence, relationLabel } from "@/lib/format";
import { MAX_EXPLAIN_EDGES } from "./schemas";
import type { AtlasNode, Edge, ExplainAudience, ExplainResponse, ExplainStep } from "./types";

/** Matches the backend's deterministic fallback: no model, one cited step per edge. */
export const TEMPLATE_PROMPT_VERSION = "template-v1";

const HYPOTHESIS_CAVEAT =
  "Steps marked hypothesis come from our pipeline (text extraction or graph analytics), not from a curated source. Check them with an expert.";
const GENERAL_CAVEAT =
  "This is a map of published evidence, not medical advice. Talk to your clinical team before acting on it.";

function nodeLabel(nodesById: Map<string, AtlasNode>, id: string): string {
  return nodesById.get(id)?.label ?? displayId(id);
}

function stepFor(edge: Edge, nodesById: Map<string, AtlasNode>, audience: ExplainAudience) {
  const source = nodeLabel(nodesById, edge.source_id);
  const target = nodeLabel(nodesById, edge.target_id);
  const relation = relationLabel(edge.relation);
  const isHypothesis = edge.evidence_type === "inferred";
  const p = edge.provenance;
  const base = `${source} ${relation} ${target}.`;
  const text =
    audience === "researcher"
      ? `${base} Source: ${p.source} ${p.source_record_id} (${edge.evidence_type}, confidence ${formatConfidence(edge.confidence)}).`
      : `${base} ${isHypothesis ? "This link is a hypothesis our pipeline suggested." : `Recorded by ${p.source}.`}`;
  const step: ExplainStep = { text, edge_ids: [edge.id], is_hypothesis: isHypothesis };
  return step;
}

/**
 * Builds the same shape the backend returns when OpenAI is unavailable: one step per known edge,
 * hypotheses flagged, source "template", ai_generated false. Throws when no edge id is known.
 */
/** Start and end node ids of a chained path, whatever direction each edge points. */
export function pathEnds(edges: readonly Edge[]): [string, string] {
  const first = edges[0];
  const last = edges[edges.length - 1];
  if (!first || !last) throw new Error("A path needs at least one link.");
  if (edges.length === 1) return [first.source_id, first.target_id];
  const second = edges[1]!;
  const prev = edges[edges.length - 2]!;
  const start = [second.source_id, second.target_id].includes(first.target_id)
    ? first.source_id
    : first.target_id;
  const end = [prev.source_id, prev.target_id].includes(last.source_id)
    ? last.target_id
    : last.source_id;
  return [start, end];
}

export function buildTemplateExplanation(
  edgeIds: string[],
  audience: ExplainAudience,
  edges: Edge[],
  nodes: AtlasNode[],
): ExplainResponse {
  const edgeById = new Map(edges.map((e) => [e.id, e]));
  const nodesById = new Map(nodes.map((n) => [n.id, n]));
  const unique = [...new Set(edgeIds.map((id) => id.trim()))].slice(0, MAX_EXPLAIN_EDGES);
  const known = unique.map((id) => edgeById.get(id)).filter((e): e is Edge => e !== undefined);
  const firstEdge = known[0];
  const lastEdge = known[known.length - 1];
  if (!firstEdge || !lastEdge) throw new Error("None of these links are in the demo data.");

  const steps = known.map((e) => stepFor(e, nodesById, audience));
  const [startId, endId] = pathEnds(known);
  const first = nodeLabel(nodesById, startId);
  const last = nodeLabel(nodesById, endId);
  const hypotheses = steps.filter((s) => s.is_hypothesis).length;
  const summary =
    `${first} connects to ${last} through ${known.length} ${known.length === 1 ? "link" : "links"}` +
    (hypotheses > 0 ? `, ${hypotheses} of them a hypothesis.` : ", all backed by recorded data.");
  const caveats = [
    ...(hypotheses > 0 ? [HYPOTHESIS_CAVEAT] : []),
    ...(known.length < unique.length
      ? [`${unique.length - known.length} cited link(s) could not be found and were skipped.`]
      : []),
    GENERAL_CAVEAT,
  ];
  return {
    steps,
    summary,
    caveats,
    source: "template",
    model: null,
    prompt_version: TEMPLATE_PROMPT_VERSION,
    ai_generated: false,
  };
}

/** Plain-text version of an explanation, for the clipboard. */
export function explanationToText(title: string, explanation: ExplainResponse): string {
  const lines = [
    title,
    "",
    explanation.summary,
    "",
    ...explanation.steps.map(
      (s, i) =>
        `${i + 1}. ${s.is_hypothesis ? "[hypothesis] " : ""}${s.text} (evidence: ${s.edge_ids.join(", ")})`,
    ),
  ];
  if (explanation.caveats.length > 0) {
    lines.push("", "Caveats:", ...explanation.caveats.map((c) => `- ${c}`));
  }
  lines.push(
    "",
    explanation.ai_generated
      ? `AI-generated (${explanation.model ?? "OpenAI"}); every step cites an atlas edge.`
      : "Template text (AI unavailable); every step cites an atlas edge.",
  );
  return lines.join("\n");
}
