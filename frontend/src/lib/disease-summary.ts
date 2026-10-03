import type { AtlasNode, Edge, NodeSummary, Relation } from "@/lib/api/types";

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

/** Neighbours joined by `relation`, either from this node ("out") or into it ("in"). */
function linked(summary: NodeSummary, relation: Relation, direction: "out" | "in"): LinkedNode[] {
  const byId = new Map(summary.neighbors.map((n) => [n.id, n]));
  const self = summary.node.id;
  return summary.edges
    .filter(
      (e) => e.relation === relation && (direction === "out" ? e.source_id : e.target_id) === self,
    )
    .flatMap((edge) => {
      const node = byId.get(direction === "out" ? edge.target_id : edge.source_id);
      return node ? [{ node, edge }] : [];
    });
}

/** Attributes are str -> str on the wire, so IC arrives as a string. */
const informationContent = (n: AtlasNode) => {
  const ic = Number(n.attributes.ic);
  return Number.isFinite(ic) ? ic : 0;
};

/** Summary-first view of a disease: cause, most informative symptoms, mechanism. */
export function buildDiseaseSummary(summary: NodeSummary): DiseaseSummary {
  return {
    // Causal genes (disease -> gene) plus risk genes (gene -> disease, backend `risk_factor_for`).
    causes: [...linked(summary, "caused_by", "out"), ...linked(summary, "risk_factor_for", "in")],
    phenotypes: linked(summary, "has_phenotype", "out")
      .sort((a, b) => informationContent(b.node) - informationContent(a.node))
      .slice(0, TOP_PHENOTYPES),
    mechanisms: linked(summary, "has_mechanism", "out"),
  };
}
