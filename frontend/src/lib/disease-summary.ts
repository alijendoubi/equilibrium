import type { AtlasNode, Edge, NodeSummary } from "@/lib/api/types";

export const TOP_PHENOTYPES = 5;

export interface LinkedNode {
  node: AtlasNode;
  edge: Edge;
}

export interface DiseaseSummary {
  causes: LinkedNode[];
  phenotypes: LinkedNode[];
  mechanisms: LinkedNode[];
}

function outgoing(summary: NodeSummary, relation: string): LinkedNode[] {
  const byId = new Map(summary.neighbors.map((n) => [n.id, n]));
  return summary.edges
    .filter((e) => e.source_id === summary.node.id && e.relation === relation)
    .flatMap((edge) => {
      const node = byId.get(edge.target_id);
      return node ? [{ node, edge }] : [];
    });
}

const informationContent = (n: AtlasNode) => {
  const ic = n.attributes?.ic;
  return typeof ic === "number" ? ic : 0;
};

/** Summary-first view of a disease: cause, most informative symptoms, mechanism. */
export function buildDiseaseSummary(summary: NodeSummary): DiseaseSummary {
  return {
    causes: outgoing(summary, "caused_by"),
    phenotypes: outgoing(summary, "has_phenotype")
      .sort((a, b) => informationContent(b.node) - informationContent(a.node))
      .slice(0, TOP_PHENOTYPES),
    mechanisms: outgoing(summary, "has_mechanism"),
  };
}
