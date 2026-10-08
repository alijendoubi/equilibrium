import type { Edge, NodeType } from "@/lib/api/types";
import { NODE_TYPE_TONE } from "@/lib/format";
import { isContradiction } from "@/lib/graph-map";

/**
 * Visual encoding of the evidence map. Colour is never the only signal: every node type has
 * its own shape and a text label, and every line style is spelled out in the legend.
 */

export const NODE_SHAPE_NAME: Record<NodeType, string> = {
  disease: "circle",
  gene: "square",
  variant: "downward triangle",
  mechanism: "hexagon",
  phenotype: "triangle",
  patient_group: "pentagon",
  funder: "diamond",
  investigator: "cross",
  asset: "star",
  study: "wide rectangle",
  publication: "page",
};

export const NODE_TYPE_PLURAL: Record<NodeType, string> = {
  disease: "diseases",
  gene: "genes",
  variant: "variants",
  mechanism: "mechanisms",
  phenotype: "symptoms",
  patient_group: "patient groups",
  publication: "publications",
  study: "studies",
  asset: "assets",
  investigator: "investigators",
  funder: "funders",
};

function polygon(points: number, radius: number, startDeg: number): string {
  const coords = Array.from({ length: points }, (_, i) => {
    const a = ((startDeg + (360 / points) * i) * Math.PI) / 180;
    return `${(Math.cos(a) * radius).toFixed(2)},${(Math.sin(a) * radius).toFixed(2)}`;
  });
  return `M${coords.join("L")}Z`;
}

function star(outer: number, inner: number): string {
  const coords = Array.from({ length: 10 }, (_, i) => {
    const radius = i % 2 === 0 ? outer : inner;
    const a = ((-90 + 36 * i) * Math.PI) / 180;
    return `${(Math.cos(a) * radius).toFixed(2)},${(Math.sin(a) * radius).toFixed(2)}`;
  });
  return `M${coords.join("L")}Z`;
}

/** SVG path for a node of `type` with nominal radius `r`, centred on (0, 0). */
export function shapePath(type: NodeType, r: number): string {
  switch (type) {
    case "disease":
      return `M${-r},0a${r},${r} 0 1,0 ${2 * r},0a${r},${r} 0 1,0 ${-2 * r},0Z`;
    case "gene": {
      const s = r * 0.88;
      return `M${-s},${-s}H${s}V${s}H${-s}Z`;
    }
    case "variant":
      return polygon(3, r * 1.25, 90);
    case "mechanism":
      return polygon(6, r * 1.08, 0);
    case "phenotype":
      return polygon(3, r * 1.25, -90);
    case "patient_group":
      return polygon(5, r * 1.12, -90);
    case "funder":
      return polygon(4, r * 1.2, -90);
    case "investigator": {
      const a = r * 0.35;
      const b = r;
      return `M${-a},${-b}H${a}V${-a}H${b}V${a}H${a}V${b}H${-a}V${a}H${-b}V${-a}H${-a}Z`;
    }
    case "asset":
      return star(r * 1.3, r * 0.58);
    case "study":
      return `M${-r * 1.35},${-r * 0.72}H${r * 1.35}V${r * 0.72}H${-r * 1.35}Z`;
    case "publication":
      return `M${-r * 0.78},${-r}H${r * 0.4}L${r * 0.78},${-r * 0.62}V${r}H${-r * 0.78}Z`;
  }
}

/** Fill colour (a CSS custom property) for a node type. */
export function nodeColor(type: NodeType): string {
  return `var(--${NODE_TYPE_TONE[type]})`;
}

export type EdgeStyle = "data" | "hypothesis" | "contradiction";

export function edgeStyle(edge: Edge, contradictionIds: ReadonlySet<string>): EdgeStyle {
  if (contradictionIds.has(edge.id) || isContradiction(edge)) return "contradiction";
  return edge.evidence_type === "inferred" ? "hypothesis" : "data";
}

/** Badge text on a contradiction line: the claim itself, or a claim someone disputes. */
export function contradictionBadge(edge: Edge): string {
  return edge.relation === "contradicts" ? "contradicts" : "contested";
}

/** Stroke width grows with confidence (1.2 at 0, 4.2 at 1). */
export function edgeWidth(confidence: number): number {
  return 1.2 + 3 * Math.max(0, Math.min(1, confidence));
}

export const DASH = "7 5";

export function truncateLabel(label: string, max = 24): string {
  return label.length > max ? `${label.slice(0, max - 1).trimEnd()}…` : label;
}
