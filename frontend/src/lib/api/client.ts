import type { z } from "zod";
import { getPublicEnv, getServerEnv } from "@/lib/env";
import { displayId } from "@/lib/format";
import { loadMockClusters, mockClusterOf, type MockClusters } from "./clusters-mock";
import { buildTemplateExplanation } from "./explain-template";
import { loadMockDataset, type MockDataset } from "./mock-data";
import {
  actionsResponseSchema,
  clusterDetailSchema,
  clustersResponseSchema,
  coverageReportSchema,
  explainResponseSchema,
  MAX_EXPLAIN_EDGES,
  nodeSummarySchema,
  pathResponseSchema,
  searchResponseSchema,
} from "./schemas";
import type {
  ActionsResponse,
  AtlasNode,
  ClusterDetail,
  ClustersResponse,
  CoverageReport,
  ExplainAudience,
  ExplainResponse,
  NodeSummary,
  Path,
  PathResponse,
  SearchResponse,
  SearchResult,
} from "./types";

/** The UI talks to the atlas only through this interface. Mock and HTTP versions are swappable. */
export interface AtlasClient {
  readonly isMock: boolean;
  /** True once any call on this client was answered from the bundled demo data. */
  readonly usedFallback: boolean;
  search(q: string): Promise<SearchResponse>;
  /** Resolves to null when the id is unknown. */
  getNode(id: string): Promise<NodeSummary | null>;
  getPath(from: string, to: string): Promise<PathResponse>;
  getActions(id: string): Promise<ActionsResponse | null>;
  getCoverage(id: string): Promise<CoverageReport | null>;
  /** Cited plain-language explanation of up to 12 edges (POST /api/v1/explain). */
  explain(edgeIds: string[], audience?: ExplainAudience): Promise<ExplainResponse>;
  /** Every disease cluster (GET /api/v1/clusters). */
  getClusters(): Promise<ClustersResponse>;
  /** Resolves to null when the cluster id is unknown. */
  getCluster(id: string): Promise<ClusterDetail | null>;
}

/** Abort a backend call after this long and fall back to the bundled demo data. */
export const API_TIMEOUT_MS = 4000;
/** Explain may call OpenAI; give it longer before falling back to the template. */
export const EXPLAIN_TIMEOUT_MS = 15000;

export const MAX_SEARCH_RESULTS = 10;
const MAX_TOP_EDGES = 25;
const MOCK_SEARCHED = ["labels", "synonyms", "descriptions (keyword stand-in for embeddings)"];

// ---------------------------------------------------------------------------------------------
// Mock client
// ---------------------------------------------------------------------------------------------

const normalize = (s: string) => s.trim().toLowerCase();

function matchNode(node: AtlasNode, q: string): SearchResult | null {
  const label = normalize(node.label);
  if (label === q || normalize(node.id) === q || normalize(displayId(node.id)) === q) {
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
  const description = node.attributes.description ?? "";
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

export function createMockClient(
  load: () => MockDataset = loadMockDataset,
  loadClusters: () => MockClusters = loadMockClusters,
): AtlasClient {
  const nodeById = (data: MockDataset, id: string) => data.nodes.find((n) => n.id === id);

  return {
    isMock: true,
    usedFallback: false,

    async getClusters() {
      return loadClusters().list;
    },

    async getCluster(id) {
      return loadClusters().details.get(id) ?? null;
    },

    async explain(edgeIds, audience = "family") {
      const data = load();
      return buildTemplateExplanation(edgeIds, audience, data.edges, data.nodes);
    },

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
        cluster_id: node.type === "disease" ? mockClusterOf(id, loadClusters()) : null,
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

export class AtlasApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "AtlasApiError";
  }
}

export interface HttpClientOptions {
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
  explainTimeoutMs?: number;
}

export function createHttpClient(baseUrl: string, options: HttpClientOptions = {}): AtlasClient {
  const fetchImpl = options.fetchImpl ?? fetch;
  const timeoutMs = options.timeoutMs ?? API_TIMEOUT_MS;
  const explainTimeoutMs = options.explainTimeoutMs ?? EXPLAIN_TIMEOUT_MS;

  async function request<T>(
    path: string,
    schema: z.ZodType<T>,
    init: RequestInit,
    timeout: number,
    allow404: boolean,
  ): Promise<T | null> {
    let res: Response;
    try {
      res = await fetchImpl(`${baseUrl}/api/v1${path}`, {
        cache: "no-store",
        ...init,
        signal: AbortSignal.timeout(timeout),
      });
    } catch (cause) {
      const reason = cause instanceof Error ? cause.message : "network error";
      throw new AtlasApiError(`Atlas API ${path} unreachable: ${reason}`, null);
    }
    if (allow404 && res.status === 404) return null;
    if (!res.ok)
      throw new AtlasApiError(`Atlas API ${path} failed with HTTP ${res.status}`, res.status);
    const parsed = schema.safeParse(await res.json());
    if (!parsed.success) {
      throw new AtlasApiError(`Atlas API ${path} returned an unexpected shape`, res.status);
    }
    return parsed.data;
  }
  const get = <T>(path: string, schema: z.ZodType<T>, allow404 = false) =>
    request(path, schema, {}, timeoutMs, allow404);
  const enc = encodeURIComponent;

  return {
    isMock: false,
    usedFallback: false,
    async explain(edgeIds, audience = "family") {
      const body = JSON.stringify({ edge_ids: edgeIds.slice(0, MAX_EXPLAIN_EDGES), audience });
      const init = { method: "POST", headers: { "Content-Type": "application/json" }, body };
      return (await request("/explain", explainResponseSchema, init, explainTimeoutMs, false))!;
    },
    async search(q) {
      return (await get(`/search?q=${enc(q)}`, searchResponseSchema))!;
    },
    getNode: (id) => get(`/nodes/${enc(id)}`, nodeSummarySchema, true),
    async getPath(from, to) {
      return (await get(`/paths?from=${enc(from)}&to=${enc(to)}&k=3`, pathResponseSchema))!;
    },
    getActions: (id) => get(`/actions/${enc(id)}`, actionsResponseSchema, true),
    getCoverage: (id) => get(`/coverage/${enc(id)}`, coverageReportSchema, true),
    async getClusters() {
      return (await get("/clusters", clustersResponseSchema))!;
    },
    getCluster: (id) => get(`/clusters/${enc(id)}`, clusterDetailSchema, true),
  };
}

/** Mocks are on unless NEXT_PUBLIC_USE_MOCKS is exactly "false". */
export function shouldUseMocks(value: string | undefined = process.env.NEXT_PUBLIC_USE_MOCKS) {
  return value?.trim().toLowerCase() !== "false";
}

/**
 * Wraps the live client: when the backend is down, times out, answers 5xx or sends an unexpected
 * shape, the call is answered from the bundled demo data and `usedFallback` flips to true so the
 * page can say "Showing cached demo data". A 404 is a real answer and is not replaced.
 */
export function createFallbackClient(primary: AtlasClient, fallback: AtlasClient): AtlasClient {
  let usedFallback = false;
  async function attempt<T>(live: () => Promise<T>, cached: () => Promise<T>): Promise<T> {
    try {
      return await live();
    } catch {
      usedFallback = true;
      return cached();
    }
  }
  return {
    isMock: false,
    get usedFallback() {
      return usedFallback;
    },
    search: (q) =>
      attempt(
        () => primary.search(q),
        () => fallback.search(q),
      ),
    getNode: (id) =>
      attempt(
        () => primary.getNode(id),
        () => fallback.getNode(id),
      ),
    getPath: (from, to) =>
      attempt(
        () => primary.getPath(from, to),
        () => fallback.getPath(from, to),
      ),
    getActions: (id) =>
      attempt(
        () => primary.getActions(id),
        () => fallback.getActions(id),
      ),
    getCoverage: (id) =>
      attempt(
        () => primary.getCoverage(id),
        () => fallback.getCoverage(id),
      ),
    explain: (ids, audience) =>
      attempt(
        () => primary.explain(ids, audience),
        () => fallback.explain(ids, audience),
      ),
    getClusters: () =>
      attempt(
        () => primary.getClusters(),
        () => fallback.getClusters(),
      ),
    getCluster: (id) =>
      attempt(
        () => primary.getCluster(id),
        () => fallback.getCluster(id),
      ),
  };
}

/** Server components may reach the backend on a private URL (BACKEND_URL, e.g. inside compose). */
export function apiBaseUrl(): string {
  const isServer = typeof window === "undefined";
  if (isServer && process.env.BACKEND_URL?.trim()) return getServerEnv().BACKEND_URL;
  return getPublicEnv().NEXT_PUBLIC_API_URL;
}

/** A fresh client per call, so `usedFallback` describes one page render or one button press. */
export function getAtlasClient(): AtlasClient {
  if (shouldUseMocks()) return mockClient;
  return createFallbackClient(createHttpClient(apiBaseUrl()), mockClient);
}
