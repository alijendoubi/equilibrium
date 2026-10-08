import type { EvidenceType, GraphMapResponse, NodeType, SearchResult } from "@/lib/api/types";

/**
 * Result of the home page "Trace it" flow: a search, then the depth-1 evidence map of the best
 * match. Shared by the server action (src/lib/trace.ts) and the client home component.
 */

export const MAX_TRACE_QUERY_LENGTH = 200;
/** Other search hits offered as "Not what you meant?" next to the traced match. */
export const MAX_ALTERNATIVES = 4;

export interface DataFlags {
  isMock: boolean;
  usedFallback: boolean;
}

export type TraceResult =
  | ({
      status: "found";
      query: string;
      match: SearchResult;
      alternatives: SearchResult[];
      /** Null when the match is in the atlas but the map service did not return it. */
      graph: GraphMapResponse | null;
    } & DataFlags)
  | ({ status: "not_found"; query: string; searched: string[] } & DataFlags)
  | { status: "invalid"; query: string; message: string }
  | { status: "error"; query: string; message: string };

export type GraphResult =
  | ({ status: "ok"; graph: GraphMapResponse | null } & DataFlags)
  | { status: "error"; message: string };

export interface TraceSummary {
  /** Neighbours of the center by type, most common first. */
  neighbours: { type: NodeType; count: number }[];
  links: number;
  contradictions: number;
  byEvidence: Partial<Record<EvidenceType, number>>;
}

/** Counts what the traced map shows, so the header can describe it in one honest line. */
export function summarizeTrace(graph: GraphMapResponse): TraceSummary {
  const counts = new Map<NodeType, number>();
  for (const { node } of graph.nodes) {
    if (node.id === graph.center) continue;
    counts.set(node.type, (counts.get(node.type) ?? 0) + 1);
  }
  const byEvidence: Partial<Record<EvidenceType, number>> = {};
  for (const edge of graph.edges) {
    byEvidence[edge.evidence_type] = (byEvidence[edge.evidence_type] ?? 0) + 1;
  }
  return {
    neighbours: [...counts.entries()]
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count || a.type.localeCompare(b.type)),
    links: graph.edges.length,
    contradictions: graph.contradiction_edge_ids.length,
    byEvidence,
  };
}

/** Trims and caps raw user input; returns "" when nothing usable is left. */
export function normalizeQuery(raw: unknown): string {
  return typeof raw === "string" ? raw.trim().slice(0, MAX_TRACE_QUERY_LENGTH) : "";
}
