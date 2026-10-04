import { z } from "zod";
import clustersJson from "@/mocks/clusters.json";
import { loadMockDataset, type MockDataset } from "./mock-data";
import { clusterDetailSchema, clustersResponseSchema, curie } from "./schemas";
import type { AtlasNode, ClusterDetail, ClusterNode, ClustersResponse } from "./types";

/**
 * Mock clusters (src/mocks/clusters.json): stored as node ids, filled in with the mock nodes and
 * validated with the same schemas as the live API. Mirrors GET /api/v1/clusters[/{id}].
 */

const storedFeature = z.object({
  node_id: curie,
  member_ids: z.array(curie),
  ic: z.number().nullable(),
});
const detailShape = clusterDetailSchema.shape;

const storedClustersSchema = z.object({
  method: clustersResponseSchema.shape.method,
  clusters: z.array(
    z.object({
      id: detailShape.id,
      label: detailShape.label,
      member_ids: detailShape.member_ids,
      features: z.object({
        genes: z.array(storedFeature),
        mechanisms: z.array(storedFeature),
        phenotypes: z.array(storedFeature),
      }),
      edges: detailShape.edges,
      bridges: detailShape.bridges,
      counterexamples: z.array(
        z.object({
          gene_id: curie,
          member_id: curie,
          other_id: curie,
          other_cluster_id: z.string().min(1),
          score: z.number().min(0).max(1),
          note: z.string(),
        }),
      ),
    }),
  ),
});

type StoredClusters = z.infer<typeof storedClustersSchema>;
type StoredCluster = StoredClusters["clusters"][number];

export interface MockClusters {
  list: ClustersResponse;
  details: Map<string, ClusterDetail>;
}

function nodeLookup(data: MockDataset) {
  const byId = new Map(data.nodes.map((n) => [n.id, n]));
  return (id: string): AtlasNode => {
    const node = byId.get(id);
    if (!node) throw new Error(`Invalid mock clusters: unknown node ${id}`);
    return node;
  };
}

function hydrate(
  cluster: StoredCluster,
  node: (id: string) => AtlasNode,
  clusterOf: Map<string, string>,
  degree: Map<string, number>,
): ClusterDetail {
  const external = [
    ...cluster.bridges.map((b) => b.other_id),
    ...cluster.counterexamples.map((c) => c.other_id),
  ].filter((id, i, all) => !cluster.member_ids.includes(id) && all.indexOf(id) === i);
  const nodes: ClusterNode[] = [...cluster.member_ids, ...external.sort()].map((id) => ({
    node: node(id),
    cluster_id: clusterOf.get(id) ?? cluster.id,
    is_member: cluster.member_ids.includes(id),
    degree: degree.get(id) ?? 0,
  }));
  const feature = (f: z.infer<typeof storedFeature>) => ({ ...f, node: node(f.node_id) });
  return clusterDetailSchema.parse({
    id: cluster.id,
    label: cluster.label,
    size: cluster.member_ids.length,
    member_ids: cluster.member_ids,
    nodes,
    features: {
      genes: cluster.features.genes.map(feature),
      mechanisms: cluster.features.mechanisms.map(feature),
      phenotypes: cluster.features.phenotypes.map(feature),
    },
    edges: cluster.edges,
    bridges: cluster.bridges,
    counterexamples: cluster.counterexamples.map(({ gene_id, ...rest }) => ({
      ...rest,
      gene: node(gene_id),
    })),
  });
}

/** Validates the stored mock clusters and fills in their nodes. Throws a readable error. */
export function parseMockClusters(raw: unknown, data: MockDataset): MockClusters {
  const parsed = storedClustersSchema.safeParse(raw);
  if (!parsed.success) {
    const details = parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`);
    throw new Error(`Invalid mock clusters: ${details.join("; ")}`);
  }
  const stored = parsed.data;
  const node = nodeLookup(data);
  const clusterOf = new Map(stored.clusters.flatMap((c) => c.member_ids.map((m) => [m, c.id])));
  const degree = new Map<string, number>();
  for (const edge of stored.clusters.flatMap((c) => c.edges)) {
    if (edge.kind !== "within") continue;
    for (const id of [edge.source_id, edge.target_id]) degree.set(id, (degree.get(id) ?? 0) + 1);
  }
  const details = new Map(
    stored.clusters.map((c) => [c.id, hydrate(c, node, clusterOf, degree)] as const),
  );
  const list: ClustersResponse = {
    method: stored.method,
    clusters: [...details.values()].map(({ id, label, size, member_ids }) => ({
      id,
      label,
      size,
      member_ids,
    })),
  };
  return { list, details };
}

let cached: MockClusters | null = null;

export function loadMockClusters(): MockClusters {
  cached ??= parseMockClusters(clustersJson, loadMockDataset());
  return cached;
}

/** The mock cluster of a disease, or null (mirrors NodeSummary.cluster_id). */
export function mockClusterOf(id: string, clusters: MockClusters = loadMockClusters()) {
  return clusters.list.clusters.find((c) => c.member_ids.includes(id))?.id ?? null;
}
