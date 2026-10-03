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

  it("uses backend id formats: CURIE node ids and E:<16 hex> edge ids", () => {
    const data = loadMockDataset();
    for (const node of data.nodes) expect(node.id).toMatch(/^[A-Za-z][A-Za-z0-9_.-]*:\S+$/);
    for (const edge of data.edges) expect(edge.id).toMatch(/^E:[0-9a-f]{16}$/);
    expect(new Set(data.edges.map((e) => e.id)).size).toBe(data.edges.length);
    expect(data.nodes.some((n) => n.id === "clinicaltrials:NCT05778617")).toBe(true);
  });

  it("gives every edge a source URL, or marks it inferred with supporting edges", () => {
    for (const edge of loadMockDataset().edges) {
      if (edge.provenance.url === null) {
        expect(edge.evidence_type).toBe("inferred");
        expect(edge.provenance.supporting_edge_ids.length).toBeGreaterThan(0);
      }
      expect(["observed", "curated", "inferred"]).toContain(edge.evidence_type);
    }
  });

  it("rejects an edge pointing to an unknown node", () => {
    const raw = clone();
    raw.edges[0] = { ...raw.edges[0], target_id: "HGNC:0000000" };
    expect(() => parseMockDataset(raw)).toThrow(/unknown node HGNC:0000000/);
  });

  it("rejects a bare NCT node id and an old-style edge id", () => {
    const raw = clone();
    raw.nodes[0] = { ...(raw.nodes[0] as object), id: "NCT05778617" };
    raw.edges[0] = { ...raw.edges[0], id: "e_gd_gba1" };
    expect(() => parseMockDataset(raw)).toThrow(/must be a CURIE/);
    expect(() => parseMockDataset(raw)).toThrow(/16 lowercase hex/);
  });

  it("rejects a curated edge without a URL", () => {
    const raw = clone();
    const first = raw.edges[0]!;
    raw.edges[0] = { ...first, provenance: { ...(first.provenance as object), url: null } };
    expect(() => parseMockDataset(raw)).toThrow(/curated edges must have provenance.url/);
  });

  it("rejects an LLM-extracted edge that is not inferred", () => {
    const raw = clone();
    const first = raw.edges[0]!;
    raw.edges[0] = {
      ...first,
      provenance: { ...(first.provenance as object), extractor: "openai:extract@v1" },
    };
    expect(() => parseMockDataset(raw)).toThrow(/LLM-extracted edges must have evidence_type/);
  });

  it("defaults fields the backend may omit", () => {
    const raw = clone();
    const { confidence_reasons, contradicted_by, qualifiers, ...rest } = raw.edges[0]!;
    void confidence_reasons;
    void contradicted_by;
    void qualifiers;
    raw.edges[0] = rest;
    const edge = parseMockDataset(raw).edges[0]!;
    expect(edge.confidence_reasons).toEqual([]);
    expect(edge.contradicted_by).toEqual([]);
    expect(edge.qualifiers).toEqual({});
    expect(edge.provenance.supporting_edge_ids).toEqual([]);
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
      pathResponseSchema.safeParse(
        await client.getPath("clinicaltrials:NCT05778617", "MONDO:0009267"),
      ).success,
    ).toBe(true);
    expect(actionsResponseSchema.safeParse(await client.getActions("MONDO:0009267")).success).toBe(
      true,
    );
  });

  it("reverses a stored path when asked from the other end", async () => {
    const res = await client.getPath("clinicaltrials:NCT05778617", "MONDO:0009267");
    expect(res.paths[0]!.nodes[0]!.id).toBe("clinicaltrials:NCT05778617");
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
