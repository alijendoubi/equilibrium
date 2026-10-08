import { CURIE_PATTERN, EDGE_ID_PATTERN } from "@/lib/api/schemas";
import type {
  AtlasNode,
  Edge,
  GraphMapResponse,
  GraphQuery,
  MapNode,
  NodeType,
} from "@/lib/api/types";

/**
 * Evidence map helpers shared by the mock client, the /map page and the map component.
 * `buildMap` mirrors backend/src/atlas/graph/evidence_map.py so mock mode behaves like the API.
 */

export const MAX_MAP_NODES = 150;
export const MAX_MAP_EDGES = 400;
export const TYPE_CAP = 30;
const TYPE_CAPS: Partial<Record<NodeType, number>> = { investigator: 12, study: 24 };
export const MAX_EXPAND = 8;
export const MAX_HIGHLIGHT = 12;

export const ALL_NODE_TYPES: NodeType[] = [
  "disease",
  "gene",
  "variant",
  "mechanism",
  "patient_group",
  "funder",
  "asset",
  "study",
  "publication",
  "investigator",
  "phenotype",
];
const TYPE_RANK = new Map(ALL_NODE_TYPES.map((t, i) => [t, i]));
const DEFAULT_COLLAPSED: ReadonlySet<NodeType> = new Set(["phenotype"]);
const OVERVIEW_TYPES: ReadonlySet<NodeType> = new Set([
  "disease",
  "gene",
  "variant",
  "mechanism",
  "patient_group",
  "asset",
  "publication",
]);
const CURATED_ASSET_ATTRIBUTE = "asset_slug";

export function isContradiction(edge: Edge): boolean {
  return edge.relation === "contradicts" || edge.contradicted_by.length > 0;
}

const otherEnd = (edge: Edge, id: string) =>
  edge.source_id === id ? edge.target_id : edge.source_id;
const ic = (node: AtlasNode) => Number(node.attributes.ic ?? 0) || 0;

interface Candidate {
  node: AtlasNode;
  distance: number | null;
  best: number;
}

function candidateCompare(a: Candidate, b: Candidate): number {
  return (
    (a.distance ?? 0) - (b.distance ?? 0) ||
    TYPE_RANK.get(a.node.type)! - TYPE_RANK.get(b.node.type)! ||
    b.best - a.best ||
    ic(b.node) - ic(a.node) ||
    a.node.label.toLowerCase().localeCompare(b.node.label.toLowerCase()) ||
    a.node.id.localeCompare(b.node.id)
  );
}

function countBy<T>(items: T[], key: (item: T) => string): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const item of items) counts[key(item)] = (counts[key(item)] ?? 0) + 1;
  return Object.fromEntries(Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)));
}

/** Builds the evidence map from an in-memory graph. Returns null for an unknown center. */
export function buildMap(
  allNodes: AtlasNode[],
  allEdges: Edge[],
  query: GraphQuery = {},
  clusterOf: (id: string) => string | null = () => null,
): GraphMapResponse | null {
  const byId = new Map(allNodes.map((n) => [n.id, n]));
  const touching = new Map<string, Edge[]>();
  for (const e of allEdges) {
    for (const id of [e.source_id, e.target_id]) touching.set(id, [...(touching.get(id) ?? []), e]);
  }
  const edgesOf = (id: string) => touching.get(id) ?? [];
  const minConfidence = query.minConfidence ?? 0;
  const edgeOk = (e: Edge) =>
    e.confidence >= minConfidence && (!query.relations || query.relations.includes(e.relation));
  const visible = (t: NodeType) =>
    query.types ? query.types.includes(t) : !DEFAULT_COLLAPSED.has(t);
  const limit = Math.max(1, Math.min(query.limit ?? MAX_MAP_NODES, MAX_MAP_NODES));
  const center = query.center ? byId.get(query.center) : undefined;
  if (query.center && !center) return null;
  const depth = query.depth ?? 1;

  const pool: Candidate[] = [];
  const hidden = new Map<string, NodeType>();
  if (center) {
    const distance = new Map<string, number>([[center.id, 0]]);
    const best = new Map<string, number>();
    let frontier = [center.id];
    for (let hop = 1; hop <= depth; hop++) {
      const reached: string[] = [];
      for (const id of frontier) {
        for (const e of edgesOf(id)) {
          if (!edgeOk(e)) continue;
          const other = otherEnd(e, id);
          if (distance.has(other)) {
            if (distance.get(other) === hop)
              best.set(other, Math.max(best.get(other)!, e.confidence));
            continue;
          }
          const node = byId.get(other)!;
          if (!visible(node.type)) {
            hidden.set(other, node.type);
            continue;
          }
          distance.set(other, hop);
          best.set(other, e.confidence);
          reached.push(other);
        }
      }
      frontier = reached.sort();
    }
    for (const [id, hops] of distance) {
      if (id !== center.id) pool.push({ node: byId.get(id)!, distance: hops, best: best.get(id)! });
    }
  } else {
    const isBase = (n: AtlasNode) =>
      OVERVIEW_TYPES.has(n.type) || (n.type === "study" && CURATED_ASSET_ATTRIBUTE in n.attributes);
    const base = new Set(allNodes.filter(isBase).map((n) => n.id));
    for (const n of allNodes) {
      const linkedFunder =
        n.type === "funder" && edgesOf(n.id).some((e) => base.has(otherEnd(e, n.id)));
      const inOverview =
        (base.has(n.id) || linkedFunder) && (!query.types || query.types.includes(n.type));
      if (inOverview) pool.push({ node: n, distance: null, best: 1 });
      else hidden.set(n.id, n.type);
    }
  }

  const chosen: Candidate[] = center ? [{ node: center, distance: 0, best: 1 }] : [];
  const perType = new Map<NodeType, number>();
  for (const c of [...pool].sort(candidateCompare)) {
    const cap = center ? (TYPE_CAPS[c.node.type] ?? TYPE_CAP) : limit;
    const used = perType.get(c.node.type) ?? 0;
    if (used >= cap || chosen.length >= limit) continue;
    perType.set(c.node.type, used + 1);
    chosen.push(c);
  }
  const ids = new Set(chosen.map((c) => c.node.id));
  const induced = () =>
    allEdges.filter((e) => ids.has(e.source_id) && ids.has(e.target_id) && edgeOk(e));

  // Contradictions are surfaced, not hidden: pull in the endpoints of contradicting edges.
  for (const e of [...induced()].sort((a, b) => a.id.localeCompare(b.id))) {
    for (const cid of e.contradicted_by) {
      const other = allEdges.find((x) => x.id === cid);
      if (!other || !edgeOk(other)) continue;
      for (const id of [other.source_id, other.target_id]) {
        const node = byId.get(id);
        if (!node || ids.has(id) || !visible(node.type) || chosen.length >= limit) continue;
        ids.add(id);
        chosen.push({ node, distance: center ? depth + 1 : null, best: other.confidence });
      }
    }
  }

  const priority = (e: Edge) => [isContradiction(e) ? 0 : 1, -e.confidence] as const;
  const kept = induced()
    .sort((a, b) => {
      const [pa, ca] = priority(a);
      const [pb, cb] = priority(b);
      return pa - pb || ca - cb || a.id.localeCompare(b.id);
    })
    .slice(0, MAX_MAP_EDGES)
    .sort(
      (a, b) =>
        a.source_id.localeCompare(b.source_id) ||
        a.relation.localeCompare(b.relation) ||
        a.target_id.localeCompare(b.target_id) ||
        a.id.localeCompare(b.id),
    );
  const keptIds = new Set(kept.map((e) => e.id));
  const touchingIds = new Set<string>();
  for (const id of ids) for (const e of edgesOf(id)) if (edgeOk(e)) touchingIds.add(e.id);
  const degree = new Map<string, number>();
  for (const e of kept) {
    degree.set(e.source_id, (degree.get(e.source_id) ?? 0) + 1);
    degree.set(e.target_id, (degree.get(e.target_id) ?? 0) + 1);
  }
  const contradicted = new Set(kept.flatMap((e) => e.contradicted_by));

  const leftOut = new Map<string, NodeType>([
    ...pool.map((c) => [c.node.id, c.node.type] as const),
    ...hidden,
  ]);
  const hiddenTypes = [...leftOut].filter(([id]) => !ids.has(id)).map(([, t]) => t);
  const byType = countBy(hiddenTypes, (t) => t);

  const nodes: MapNode[] = chosen
    .sort(
      (a, b) =>
        (a.distance ?? 0) - (b.distance ?? 0) ||
        TYPE_RANK.get(a.node.type)! - TYPE_RANK.get(b.node.type)! ||
        a.node.label.toLowerCase().localeCompare(b.node.label.toLowerCase()) ||
        a.node.id.localeCompare(b.node.id),
    )
    .map((c) => ({
      node: c.node,
      degree: degree.get(c.node.id) ?? 0,
      total_degree: edgesOf(c.node.id).length,
      cluster_id: c.node.type === "disease" ? clusterOf(c.node.id) : null,
      distance: c.distance,
    }));

  return {
    center: center?.id ?? null,
    depth: center ? depth : 0,
    nodes,
    edges: kept,
    contradiction_edge_ids: kept
      .filter((e) => isContradiction(e) || contradicted.has(e.id))
      .map((e) => e.id)
      .sort(),
    truncated: {
      by_type: byType,
      nodes_hidden: hiddenTypes.length,
      edges_hidden: [...touchingIds].filter((id) => !keptIds.has(id)).length,
    },
    legend: {
      node_types: countBy(nodes, (n) => n.node.type),
      relations: countBy(kept, (e) => e.relation),
      evidence_types: countBy(kept, (e) => e.evidence_type),
    },
  };
}

/**
 * Adds the neighbourhoods of expanded nodes to a base map. Expansion centers are kept first,
 * then the rest up to the caps; highlighted edges are kept before other edges.
 */
export function mergeMaps(
  base: GraphMapResponse,
  extras: GraphMapResponse[],
  highlight: ReadonlySet<string> = new Set(),
): GraphMapResponse {
  if (extras.length === 0) return base;
  const nodes = new Map(base.nodes.map((n) => [n.node.id, n]));
  const add = (n: MapNode) => {
    if (!nodes.has(n.node.id) && nodes.size < MAX_MAP_NODES) {
      nodes.set(n.node.id, { ...n, distance: base.center ? (n.distance ?? 0) + 1 : null });
    }
  };
  for (const extra of extras) extra.nodes.filter((n) => n.node.id === extra.center).forEach(add);
  for (const extra of extras) extra.nodes.forEach(add);
  const edges = new Map<string, Edge>();
  for (const e of [base, ...extras].flatMap((m) => m.edges)) {
    if (nodes.has(e.source_id) && nodes.has(e.target_id)) edges.set(e.id, e);
  }
  const kept = [...edges.values()]
    .sort(
      (a, b) =>
        Number(highlight.has(b.id)) - Number(highlight.has(a.id)) ||
        Number(isContradiction(b)) - Number(isContradiction(a)) ||
        b.confidence - a.confidence ||
        a.id.localeCompare(b.id),
    )
    .slice(0, MAX_MAP_EDGES);
  const degree = new Map<string, number>();
  for (const e of kept) {
    degree.set(e.source_id, (degree.get(e.source_id) ?? 0) + 1);
    degree.set(e.target_id, (degree.get(e.target_id) ?? 0) + 1);
  }
  const mergedNodes = [...nodes.values()].map((n) => ({
    ...n,
    degree: degree.get(n.node.id) ?? 0,
  }));
  const contradictions = new Set([base, ...extras].flatMap((m) => m.contradiction_edge_ids));
  return {
    ...base,
    nodes: mergedNodes,
    edges: kept,
    contradiction_edge_ids: kept.filter((e) => contradictions.has(e.id)).map((e) => e.id),
    legend: {
      node_types: countBy(mergedNodes, (n) => n.node.type),
      relations: countBy(kept, (e) => e.relation),
      evidence_types: countBy(kept, (e) => e.evidence_type),
    },
  };
}

export interface MapParams {
  center?: string | null;
  depth?: 1 | 2;
  phenotypes?: boolean;
  expand?: string[];
  highlight?: string[];
}

/** URL of the /map page. Ids are URL-encoded, so "MONDO:0009266" -> "MONDO%3A0009266". */
export function mapHref({ center, depth, phenotypes, expand, highlight }: MapParams = {}): string {
  const params = new URLSearchParams();
  if (center) params.set("center", center);
  if (depth === 2) params.set("depth", "2");
  if (phenotypes) params.set("phenotypes", "1");
  if (expand && expand.length > 0) params.set("expand", expand.join(","));
  if (highlight && highlight.length > 0) params.set("highlight", highlight.join(","));
  const query = params.toString();
  return query ? `/map?${query}` : "/map";
}

const splitList = (raw: string) =>
  raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);

/** Validates /map search params; drops anything that is not a CURIE / edge id. */
export function parseMapParams(raw: Record<string, string>): Required<MapParams> {
  const center = CURIE_PATTERN.test(raw.center ?? "") ? raw.center! : null;
  return {
    center,
    depth: raw.depth === "2" ? 2 : 1,
    phenotypes: raw.phenotypes === "1",
    expand: [...new Set(splitList(raw.expand ?? "").filter((id) => CURIE_PATTERN.test(id)))]
      .filter((id) => id !== center)
      .slice(0, MAX_EXPAND),
    highlight: [
      ...new Set(splitList(raw.highlight ?? "").filter((id) => EDGE_ID_PATTERN.test(id))),
    ].slice(0, MAX_HIGHLIGHT),
  };
}
