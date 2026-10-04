import type { AtlasClient } from "@/lib/api/client";
import { MAX_EXPLAIN_EDGES } from "@/lib/api/schemas";
import type {
  ActionsResponse,
  AtlasNode,
  CoverageReport,
  Edge,
  NodeSummary,
} from "@/lib/api/types";

export interface ActionView {
  summary: NodeSummary;
  actions: ActionsResponse;
  coverage: CoverageReport | null;
  edges: Edge[];
  nodes: AtlasNode[];
  briefEdgeIds: Record<string, string[]>;
}

function uniqueById<T extends { id: string }>(items: T[]): T[] {
  return [...new Map(items.map((i) => [i.id, i])).values()];
}

/**
 * Everything the action view needs: the disease, its actions, and the strongest route to each
 * partner and asset (those route edges are what "Draft collaboration brief" explains).
 */
export async function loadActionView(client: AtlasClient, id: string): Promise<ActionView | null> {
  const [summary, actions] = await Promise.all([client.getNode(id), client.getActions(id)]);
  if (!summary || !actions) return null;

  const targets = [...new Set([...actions.partners, ...actions.assets].map((t) => t.node.id))];
  const routes = await Promise.all(targets.map((t) => client.getPath(id, t)));
  const briefEdgeIds: Record<string, string[]> = {};
  targets.forEach((t, i) => {
    const best = routes[i]?.paths[0];
    if (best) briefEdgeIds[t] = best.edges.map((e) => e.id).slice(0, MAX_EXPLAIN_EDGES);
  });

  const routeEdges = routes.flatMap((r) => r.paths.flatMap((p) => p.edges));
  const routeNodes = routes.flatMap((r) => r.paths.flatMap((p) => p.nodes));
  const itemNodes = [...actions.partners, ...actions.assets].map((t) => t.node);
  const coverage =
    actions.coverage ?? (summary.coverage_status === "gap" ? await client.getCoverage(id) : null);

  return {
    summary,
    actions,
    coverage,
    edges: uniqueById([...summary.edges, ...routeEdges]),
    nodes: uniqueById([summary.node, ...summary.neighbors, ...routeNodes, ...itemNodes]),
    briefEdgeIds,
  };
}
