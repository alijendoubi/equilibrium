import { describe, expect, it } from "vitest";
import { createMockClient, shouldUseMocks } from "@/lib/api/client";
import { RAW_MOCK_DATA, loadMockDataset, parseMockDataset } from "@/lib/api/mock-data";
import { actionsResponseSchema, nodeSummarySchema, pathResponseSchema } from "@/lib/api/schemas";

type Raw = { nodes: unknown[]; edges: Array<Record<string, unknown>> };
const clone = () => structuredClone(RAW_MOCK_DATA) as Raw;

describe("mock data", () => {
  it("passes zod validation and referential checks", () => {
    const data = loadMockDataset();
    expect(data.nodes.length).toBeGreaterThan(10);
    expect(data.edges.length).toBeGreaterThan(10);
  });

  it("gives every edge a source URL or marks it as analytics, plus an evidence type", () => {
    for (const edge of loadMockDataset().edges) {
      expect(edge.provenance.url !== null || edge.provenance.source === "analytics").toBe(true);
      expect(["observed", "curated", "inferred"]).toContain(edge.evidence_type);
    }
  });

  it("rejects an edge pointing to an unknown node", () => {
    const raw = clone();
    raw.edges[0] = { ...raw.edges[0], target_id: "HGNC:0000000" };
    expect(() => parseMockDataset(raw)).toThrow(/unknown node HGNC:0000000/);
  });

  it("rejects a non-analytics edge without a URL", () => {
    const raw = clone();
    const first = raw.edges[0]!;
    raw.edges[0] = { ...first, provenance: { ...(first.provenance as object), url: null } };
    expect(() => parseMockDataset(raw)).toThrow(/url is required/);
  });

  it("rejects an invalid evidence type", () => {
    const raw = clone();
    raw.edges[0] = { ...raw.edges[0], evidence_type: "rumour" };
    expect(() => parseMockDataset(raw)).toThrow(/Invalid mock data/);
  });
});

describe("mock client", () => {
  const client = createMockClient();

  it("returns API-shaped node, path and actions responses", async () => {
    expect(nodeSummarySchema.safeParse(await client.getNode("MONDO:0009267")).success).toBe(true);
    expect(
      pathResponseSchema.safeParse(await client.getPath("NCT05778617", "MONDO:0009267")).success,
    ).toBe(true);
    expect(actionsResponseSchema.safeParse(await client.getActions("MONDO:0009267")).success).toBe(
      true,
    );
  });

  it("reverses a stored path when asked from the other end", async () => {
    const res = await client.getPath("NCT05778617", "MONDO:0009267");
    expect(res.paths[0]!.nodes[0]!.id).toBe("NCT05778617");
    expect(res.paths[0]!.nodes.at(-1)!.id).toBe("MONDO:0009267");
  });

  it("returns null for unknown nodes", async () => {
    expect(await client.getNode("MONDO:9999999")).toBeNull();
    expect(await client.getActions("HGNC:4177")).toBeNull();
  });

  it("uses mocks unless NEXT_PUBLIC_USE_MOCKS is false", () => {
    expect(shouldUseMocks(undefined)).toBe(true);
    expect(shouldUseMocks("true")).toBe(true);
    expect(shouldUseMocks("false")).toBe(false);
    expect(shouldUseMocks(" FALSE ")).toBe(false);
  });
});
