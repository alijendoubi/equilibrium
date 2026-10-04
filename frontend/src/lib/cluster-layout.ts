import type { ClusterDetail, ClusterEdge, ClusterNode } from "@/lib/api/types";

/** Deterministic circular layout for the small cluster graph (no force simulation, no deps). */

export const GRAPH_SIZE = 520;
export const MAX_GRAPH_NODES = 25;
const CENTER = GRAPH_SIZE / 2;
const INNER_RADIUS = 140;
const OUTER_RADIUS = 215;
const BASE_NODE_RADIUS = 7;
const RADIUS_PER_LINK = 2;
const MAX_RADIUS_LINKS = 6;
const MAX_LABEL_LENGTH = 26;

/** Existing design tokens, cycled by cluster number. Colour is never the only signal. */
export const CLUSTER_COLORS = [
  "var(--cluster)",
  "var(--action)",
  "var(--evidence)",
  "var(--focus)",
  "var(--muted)",
] as const;

export interface PlacedNode {
  item: ClusterNode;
  x: number;
  y: number;
  r: number;
  color: string;
  shortLabel: string;
}

export interface PlacedEdge {
  edge: ClusterEdge;
  source: PlacedNode;
  target: PlacedNode;
}

export interface ClusterLayout {
  nodes: PlacedNode[];
  edges: PlacedEdge[];
  /** Nodes left out because the graph is capped at MAX_GRAPH_NODES. */
  hidden: number;
}

/** "C3" -> the 3rd colour; unknown ids fall back to the last (muted) colour. */
export function clusterColor(clusterId: string): string {
  const n = Number.parseInt(clusterId.replace(/^\D+/, ""), 10);
  const fallback = "var(--muted)";
  if (!Number.isFinite(n) || n < 1) return fallback;
  return CLUSTER_COLORS[(n - 1) % CLUSTER_COLORS.length] ?? fallback;
}

export function shortLabel(label: string, max = MAX_LABEL_LENGTH): string {
  return label.length <= max ? label : `${label.slice(0, max - 1).trimEnd()}…`;
}

export function nodeRadius(degree: number): number {
  return BASE_NODE_RADIUS + RADIUS_PER_LINK * Math.min(Math.max(degree, 0), MAX_RADIUS_LINKS);
}

function ring(count: number, radius: number, offset = 0): Array<{ x: number; y: number }> {
  if (count === 1 && radius === INNER_RADIUS) return [{ x: CENTER, y: CENTER }];
  return Array.from({ length: count }, (_, i) => {
    const angle = -Math.PI / 2 + offset + (2 * Math.PI * i) / count;
    const round = (v: number) => Math.round(v * 10) / 10;
    return {
      x: round(CENTER + radius * Math.cos(angle)),
      y: round(CENTER + radius * Math.sin(angle)),
    };
  });
}

/** Members on the inner circle (in API order), other clusters' diseases on the outer ring. */
export function layoutCluster(detail: ClusterDetail): ClusterLayout {
  const members = detail.nodes.filter((n) => n.is_member);
  const others = detail.nodes.filter((n) => !n.is_member);
  const shown = [...members, ...others].slice(0, MAX_GRAPH_NODES);
  const shownMembers = shown.filter((n) => n.is_member);
  const shownOthers = shown.filter((n) => !n.is_member);
  const positions = [
    ...ring(shownMembers.length, INNER_RADIUS),
    ...ring(shownOthers.length, OUTER_RADIUS, Math.PI / Math.max(shownOthers.length, 1)),
  ];
  const nodes: PlacedNode[] = [...shownMembers, ...shownOthers].map((item, i) => ({
    item,
    ...(positions[i] ?? { x: CENTER, y: CENTER }),
    r: nodeRadius(item.degree),
    color: clusterColor(item.cluster_id),
    shortLabel: shortLabel(item.node.label),
  }));
  const byId = new Map(nodes.map((n) => [n.item.node.id, n]));
  const edges: PlacedEdge[] = [];
  for (const edge of detail.edges) {
    const source = byId.get(edge.source_id);
    const target = byId.get(edge.target_id);
    if (source && target) edges.push({ edge, source, target });
  }
  return { nodes, edges, hidden: detail.nodes.length - shown.length };
}
