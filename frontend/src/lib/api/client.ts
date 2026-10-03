import type { z } from "zod";
import { getPublicEnv } from "@/lib/env";
import { loadMockDataset, type MockDataset } from "./mock-data";
import {
  actionsResponseSchema,
  coverageReportSchema,
  nodeSummarySchema,
  pathResponseSchema,
  searchResponseSchema,
} from "./schemas";
import type {
  ActionsResponse,
  AtlasNode,
  CoverageReport,
  NodeSummary,
  Path,
  PathResponse,
  SearchResponse,
  SearchResult,
} from "./types";

/** The UI talks to the atlas only through this interface. Mock and HTTP versions are swappable. */
export interface AtlasClient {
  readonly isMock: boolean;
  search(q: string): Promise<SearchResponse>;
  /** Resolves to null when the id is unknown. */
  getNode(id: string): Promise<NodeSummary | null>;
  getPath(from: string, to: string): Promise<PathResponse>;
  getActions(id: string): Promise<ActionsResponse | null>;
  getCoverage(id: string): Promise<CoverageReport | null>;
}

export const MAX_SEARCH_RESULTS = 10;
const MAX_TOP_EDGES = 25;
const MOCK_SEARCHED = ["labels", "synonyms", "descriptions (keyword stand-in for embeddings)"];

// ---------------------------------------------------------------------------------------------
// Mock client
// ---------------------------------------------------------------------------------------------

const normalize = (s: string) => s.trim().toLowerCase();

function matchNode(node: AtlasNode, q: string): SearchResult | null {
  const label = normalize(node.label);
  if (label === q || normalize(node.id) === q) {
    return { node, score: 1, match_reason: "exact", matched_text: node.label };
  }
  if (label.includes(q)) {
    return { node, score: 0.9, match_reason: "exact", matched_text: node.label };
  }
  const synonym = node.synonyms.find((s) => normalize(s).includes(q));
  if (synonym) {
    const score = normalize(synonym) === q ? 0.85 : 0.75;
    return { node, score, match_reason: "synonym", matched_text: synonym };
  }
  const words = q.split(/\s+/).filter((w) => w.length > 3);
  const description = node.description ?? "";
  const hits = words.filter((w) => normalize(description).includes(w));
  if (words.length > 0 && hits.length > 0) {
    const score = 0.4 * (hits.length / words.length);
    return { node, score, match_reason: "semantic", matched_text: hits.join(", ") };
  }
  return null;
}

function hydratePath(data: MockDataset, nodeIds: string[], edgeIds: string[]): Path {
  const nodes = nodeIds.map((id) => data.nodes.find((n) => n.id === id)!);
  const edges = edgeIds.map((id) => data.edges.find((e) => e.id === id)!);
  return {
    nodes,
    edges,
    cost: Number(edges.reduce((sum, e) => sum - Math.log(e.confidence), 0).toFixed(3)),
    has_inferred: edges.some((e) => e.evidence_type === "inferred"),
    has_contradiction: edges.some((e) => e.contradicted_by.length > 0),
  };
}

/** Finds stored demo paths that contain both ids and slices them (reversing if needed). */
function findPaths(data: MockDataset, from: string, to: string): Path[] {
  const found: Path[] = [];
  for (const stored of data.paths) {
    const i = stored.node_ids.indexOf(from);
    const j = stored.node_ids.indexOf(to);
    if (i < 0 || j < 0 || i === j) continue;
    const lo = Math.min(i, j);
    const hi = Math.max(i, j);
    let nodeIds = stored.node_ids.slice(lo, hi + 1);
    let edgeIds = stored.edge_ids.slice(lo, hi);
    if (i > j) {
      nodeIds = [...nodeIds].reverse();
      edgeIds = [...edgeIds].reverse();
    }
    found.push(hydratePath(data, nodeIds, edgeIds));
  }
  return found.sort((a, b) => a.cost - b.cost);
}

function coverageFor(data: MockDataset, id: string): CoverageReport | null {
  return data.coverage.find((c) => c.query === id) ?? null;
}

function genericGap(query: string): CoverageReport {
  return {
    query,
    result: "no_supported_route",
    searched: [{ source: "mock dataset", source_version: "MOCK", records_found: 0 }],
    not_searched: ["the live snapshot (mocks are on)"],
    missing_evidence: ["This connection is not in the mock dataset"],
    weak_leads: [],
    next_questions: [],
  };
}

export function createMockClient(load: () => MockDataset = loadMockDataset): AtlasClient {
  const nodeById = (data: MockDataset, id: string) => data.nodes.find((n) => n.id === id);

  return {
    isMock: true,

    async search(raw) {
      const data = load();
      const q = normalize(raw);
      if (!q) return { query: raw, results: [], searched: MOCK_SEARCHED };
      const results = data.nodes
        .map((n) => matchNode(n, q))
        .filter((r): r is SearchResult => r !== null)
        .sort((a, b) => b.score - a.score || a.node.label.localeCompare(b.node.label))
        .slice(0, MAX_SEARCH_RESULTS);
      return { query: raw, results, searched: MOCK_SEARCHED };
    },

    async getNode(id) {
      const data = load();
      const node = nodeById(data, id);
      if (!node) return null;
      const edges = data.edges
        .filter((e) => e.source_id === id || e.target_id === id)
        .sort((a, b) => b.confidence - a.confidence);
      const neighborIds = new Set(
        edges.map((e) => (e.source_id === id ? e.target_id : e.source_id)),
      );
      const byRelation: Record<string, number> = {};
      for (const e of edges) byRelation[e.relation] = (byRelation[e.relation] ?? 0) + 1;
      const coverage = coverageFor(data, id);
      return {
        node,
        counts: { edges: edges.length, by_relation: byRelation },
        edges: edges.slice(0, MAX_TOP_EDGES),
        neighbors: data.nodes.filter((n) => neighborIds.has(n.id)),
        cluster_id: node.type === "disease" && !coverage ? "cluster:gba1_lysosomal" : null,
        coverage_status: coverage ? "gap" : "supported",
      };
    },

    async getPath(from, to) {
      const data = load();
      const paths = findPaths(data, from, to);
      return {
        from,
        to,
        paths,
        coverage: paths.length > 0 ? null : (coverageFor(data, from) ?? genericGap(from)),
      };
    },

    async getActions(id) {
      const data = load();
      const node = nodeById(data, id);
      if (!node || node.type !== "disease") return null;
      const stored = data.actions.find((a) => a.disease_id === id);
      if (!stored) {
        return {
          disease_id: id,
          partners: [],
          assets: [],
          next_experiment: null,
          review_checklist: [],
          coverage: coverageFor(data, id) ?? genericGap(id),
        };
      }
      return {
        disease_id: id,
        partners: stored.partners.map(({ node_id, ...rest }) => ({
          ...rest,
          node: nodeById(data, node_id)!,
        })),
        assets: stored.assets.map(({ node_id, ...rest }) => ({
          ...rest,
          node: nodeById(data, node_id)!,
        })),
        next_experiment: stored.next_experiment,
        review_checklist: stored.review_checklist,
        coverage: coverageFor(data, id),
      };
    },

    async getCoverage(id) {
      return coverageFor(load(), id);
    },
  };
}

export const mockClient: AtlasClient = createMockClient();

// ---------------------------------------------------------------------------------------------
// HTTP client (for when the API is live). Validates every response with the same schemas.
// ---------------------------------------------------------------------------------------------

export function createHttpClient(baseUrl: string, fetchImpl: typeof fetch = fetch): AtlasClient {
  async function get<T>(path: string, schema: z.ZodType<T>, allow404 = false): Promise<T | null> {
    const res = await fetchImpl(`${baseUrl}/api/v1${path}`, { cache: "no-store" });
    if (allow404 && res.status === 404) return null;
    if (!res.ok) throw new Error(`Atlas API ${path} failed with HTTP ${res.status}`);
    const parsed = schema.safeParse(await res.json());
    if (!parsed.success) throw new Error(`Atlas API ${path} returned an unexpected shape`);
    return parsed.data;
  }
  const enc = encodeURIComponent;

  return {
    isMock: false,
    async search(q) {
      return (await get(`/search?q=${enc(q)}`, searchResponseSchema))!;
    },
    getNode: (id) => get(`/nodes/${enc(id)}`, nodeSummarySchema, true),
    async getPath(from, to) {
      return (await get(`/paths?from=${enc(from)}&to=${enc(to)}&k=3`, pathResponseSchema))!;
    },
    getActions: (id) => get(`/actions/${enc(id)}`, actionsResponseSchema, true),
    getCoverage: (id) => get(`/coverage/${enc(id)}`, coverageReportSchema, true),
  };
}

/** Mocks are on unless NEXT_PUBLIC_USE_MOCKS is exactly "false". */
export function shouldUseMocks(value: string | undefined = process.env.NEXT_PUBLIC_USE_MOCKS) {
  return value?.trim().toLowerCase() !== "false";
}

export function getAtlasClient(): AtlasClient {
  if (shouldUseMocks()) return mockClient;
  return createHttpClient(getPublicEnv().NEXT_PUBLIC_API_URL);
}
