import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createFallbackClient,
  createHttpClient,
  createMockClient,
  mockClient,
} from "@/lib/api/client";
import { loadMockClusters, mockClusterOf, parseMockClusters } from "@/lib/api/clusters-mock";
import { loadMockDataset } from "@/lib/api/mock-data";
import { clusterDetailSchema, clustersResponseSchema } from "@/lib/api/schemas";
import type { ClusterDetail } from "@/lib/api/types";
import clustersJson from "@/mocks/clusters.json";
import {
  clusterColor,
  layoutCluster,
  MAX_GRAPH_NODES,
  nodeRadius,
  shortLabel,
} from "@/lib/cluster-layout";

const BASE = "http://atlas.test";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockDetail(id = "C1"): ClusterDetail {
  return structuredClone(loadMockClusters().details.get(id)!);
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("cluster schemas", () => {
  it("accept the mock list and detail", () => {
    expect(clustersResponseSchema.safeParse(loadMockClusters().list).success).toBe(true);
    expect(clusterDetailSchema.safeParse(mockDetail()).success).toBe(true);
  });

  it("reject an unknown edge kind, a score above 1 and a non-CURIE member", () => {
    const badKind = mockDetail();
    badKind.edges[0] = { ...badKind.edges[0]!, kind: "dotted" as "within" };
    expect(clusterDetailSchema.safeParse(badKind).success).toBe(false);
    const badScore = mockDetail();
    badScore.bridges[0] = { ...badScore.bridges[0]!, score: 1.5 };
    expect(clusterDetailSchema.safeParse(badScore).success).toBe(false);
    const badMember = mockDetail();
    badMember.member_ids = ["not a curie"];
    expect(clusterDetailSchema.safeParse(badMember).success).toBe(false);
  });

  it("defaults a missing feature ic to null", () => {
    const raw = mockDetail() as unknown as {
      features: { genes: Array<Record<string, unknown>> };
    };
    delete raw.features.genes[0]!.ic;
    const parsed = clusterDetailSchema.parse(raw);
    expect(parsed.features.genes[0]!.ic).toBeNull();
  });
});

describe("mock clusters", () => {
  it("partition the mock diseases consistently with the real snapshot", () => {
    const { list } = loadMockClusters();
    expect(list.clusters.map((c) => c.id)).toEqual(["C1", "C2"]);
    expect(mockClusterOf("MONDO:0009266")).toBe("C1");
    expect(mockClusterOf("MONDO:0008199")).toBe("C1");
    expect(mockClusterOf("MONDO:0012517")).toBe("C2");
    expect(mockClusterOf("HGNC:4177")).toBeNull();
  });

  it("fill in nodes, degrees and the far ends of bridges", () => {
    const detail = mockDetail("C1");
    const far = detail.nodes.find((n) => !n.is_member);
    expect(far?.node.id).toBe("MONDO:0012517");
    expect(far?.cluster_id).toBe("C2");
    const member = detail.nodes.find((n) => n.node.id === "MONDO:0009266");
    expect(member?.degree).toBe(3);
    expect(detail.features.genes[0]?.node.label).toBe("GBA1");
  });

  it("reject a reference to an unknown node", () => {
    const raw = structuredClone(clustersJson) as { clusters: Array<{ member_ids: string[] }> };
    raw.clusters[0]!.member_ids = [...raw.clusters[0]!.member_ids, "MONDO:9999999"];
    expect(() => parseMockClusters(raw, loadMockDataset())).toThrow(/unknown node MONDO:9999999/);
  });

  it("reject a malformed file with a readable error", () => {
    expect(() => parseMockClusters({ clusters: "nope" }, loadMockDataset())).toThrow(
      /Invalid mock clusters/,
    );
  });

  it("are served by the mock client, including cluster_id on disease nodes", async () => {
    const client = createMockClient();
    expect((await client.getClusters()).clusters).toHaveLength(2);
    expect((await client.getCluster("C1"))?.label).toMatch(/^GBA1/);
    expect(await client.getCluster("C99")).toBeNull();
    expect((await client.getNode("MONDO:0009267"))?.cluster_id).toBe("C1");
    expect((await client.getNode("HGNC:4177"))?.cluster_id).toBeNull();
  });
});

describe("HTTP cluster client", () => {
  it("encodes the cluster id and validates the answer", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(mockDetail()));
    const client = createHttpClient(BASE, { fetchImpl });
    const detail = await client.getCluster("C1/x");
    expect(detail?.id).toBe("C1");
    expect(fetchImpl.mock.calls[0]![0]).toBe(`${BASE}/api/v1/clusters/C1%2Fx`);
  });

  it("treats 404 as an unknown cluster and falls back to mocks on 5xx", async () => {
    const notFound = createHttpClient(BASE, {
      fetchImpl: vi.fn().mockResolvedValue(jsonResponse({ detail: "unknown" }, 404)),
    });
    expect(await notFound.getCluster("C9")).toBeNull();
    const down = createFallbackClient(
      createHttpClient(BASE, {
        fetchImpl: vi.fn().mockResolvedValue(jsonResponse({ detail: "boom" }, 503)),
      }),
      mockClient,
    );
    expect((await down.getClusters()).clusters[0]?.id).toBe("C1");
    expect((await down.getCluster("C2"))?.size).toBe(1);
    expect(down.usedFallback).toBe(true);
  });

  it("falls back when the list has an unexpected shape", async () => {
    const client = createFallbackClient(
      createHttpClient(BASE, { fetchImpl: vi.fn().mockResolvedValue(jsonResponse({ x: 1 })) }),
      mockClient,
    );
    expect((await client.getClusters()).clusters.length).toBeGreaterThan(0);
    expect(client.usedFallback).toBe(true);
  });
});

describe("cluster layout", () => {
  it("is deterministic and puts members on the inner circle", () => {
    const detail = mockDetail("C1");
    const first = layoutCluster(detail);
    expect(layoutCluster(mockDetail("C1"))).toEqual(first);
    expect(first.nodes.map((n) => n.item.is_member)).toEqual([true, true, true, true, false]);
    const centre = 260;
    const dist = (n: { x: number; y: number }) => Math.hypot(n.x - centre, n.y - centre);
    expect(dist(first.nodes[0]!)).toBeLessThan(dist(first.nodes[4]!));
    expect(first.edges.filter((e) => e.edge.kind === "bridge")).toHaveLength(1);
  });

  it("centres a single member and caps the graph size", () => {
    const single = layoutCluster(mockDetail("C2"));
    expect(single.nodes[0]).toMatchObject({ x: 260, y: 260 });
    const big = mockDetail("C1");
    const template = big.nodes[0]!;
    big.nodes = Array.from({ length: 30 }, (_, i) => ({
      ...template,
      node: { ...template.node, id: `MONDO:${String(i).padStart(7, "0")}` },
    }));
    const layout = layoutCluster(big);
    expect(layout.nodes).toHaveLength(MAX_GRAPH_NODES);
    expect(layout.hidden).toBe(5);
  });

  it("maps cluster ids to tokens and sizes nodes by degree", () => {
    expect(clusterColor("C1")).toBe("var(--cluster)");
    expect(clusterColor("C6")).toBe("var(--cluster)");
    expect(clusterColor("weird")).toBe("var(--muted)");
    expect(nodeRadius(0)).toBeLessThan(nodeRadius(3));
    expect(nodeRadius(50)).toBe(nodeRadius(6));
    expect(shortLabel("short")).toBe("short");
    expect(shortLabel("x".repeat(40))).toHaveLength(26);
  });
});
