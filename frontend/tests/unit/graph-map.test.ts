import { describe, expect, it, vi } from "vitest";
import {
  createFallbackClient,
  createHttpClient,
  graphQueryString,
  mockClient,
} from "@/lib/api/client";
import { graphMapResponseSchema } from "@/lib/api/schemas";
import type { GraphMapResponse } from "@/lib/api/types";
import {
  MAX_EXPAND,
  MAX_MAP_EDGES,
  MAX_MAP_NODES,
  isContradiction,
  mapHref,
  mergeMaps,
  parseMapParams,
} from "@/lib/graph-map";
import { labelBox, placeLabels } from "@/lib/map-labels";
import { MAX_TICKS, computeLayout } from "@/lib/map-layout";

const GAUCHER_2 = "MONDO:0009266";
const GAUCHER_3 = "MONDO:0009267";
const PD24 = "MONDO:0859183";
const GBA1 = "HGNC:4177";
const PSAP = "HGNC:9498";

async function map(query: Parameters<typeof mockClient.getGraph>[0] = {}) {
  const result = await mockClient.getGraph(query);
  if (!result) throw new Error("expected a map");
  return result;
}

const ids = (m: GraphMapResponse) => m.nodes.map((n) => n.node.id);

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("graph map schema", () => {
  it("accepts the mock map and fills defaults", async () => {
    const m = await map({ center: GAUCHER_2 });
    const parsed = graphMapResponseSchema.parse(JSON.parse(JSON.stringify(m)));
    expect(parsed.center).toBe(GAUCHER_2);
    const minimal = graphMapResponseSchema.parse({
      center: null,
      depth: 0,
      nodes: [{ node: { id: GBA1, type: "gene", label: "GBA1" }, degree: 0, total_degree: 3 }],
      edges: [],
      truncated: { by_type: {}, nodes_hidden: 0, edges_hidden: 0 },
      legend: { node_types: { gene: 1 }, relations: {}, evidence_types: {} },
    });
    expect(minimal.contradiction_edge_ids).toEqual([]);
    expect(minimal.nodes[0]!.cluster_id).toBeNull();
    expect(minimal.nodes[0]!.distance).toBeNull();
  });

  it("rejects a bad center id and negative counts", () => {
    const base = {
      center: "not a curie",
      depth: 1,
      nodes: [],
      edges: [],
      truncated: { by_type: {}, nodes_hidden: 0, edges_hidden: 0 },
      legend: { node_types: {}, relations: {}, evidence_types: {} },
    };
    expect(graphMapResponseSchema.safeParse(base).success).toBe(false);
    const negative = { ...base, center: null, truncated: { ...base.truncated, nodes_hidden: -1 } };
    expect(graphMapResponseSchema.safeParse(negative).success).toBe(false);
  });
});

describe("mock evidence map (mirrors the backend)", () => {
  it("centres on Gaucher type II with GBA1 and its caused_by edge", async () => {
    const m = await map({ center: GAUCHER_2 });
    expect(ids(m)[0]).toBe(GAUCHER_2);
    expect(m.nodes[0]!.distance).toBe(0);
    expect(ids(m)).toContain(GBA1);
    expect(
      m.edges.some(
        (e) => e.relation === "caused_by" && e.source_id === GAUCHER_2 && e.target_id === GBA1,
      ),
    ).toBe(true);
    expect(m.nodes.every((n) => n.node.type !== "phenotype")).toBe(true);
    expect(m.truncated.by_type.phenotype).toBeGreaterThan(0);
  });

  it("draws phenotypes when asked", async () => {
    const m = await map({ center: GAUCHER_3, types: ["phenotype", "gene", "disease"] });
    expect(m.nodes.some((n) => n.node.type === "phenotype")).toBe(true);
    expect(m.truncated.by_type.phenotype ?? 0).toBe(0);
  });

  it("returns the overview without phenotypes", async () => {
    const m = await map();
    expect(m.center).toBeNull();
    expect(ids(m)).toEqual(expect.arrayContaining([GBA1, PSAP, "MONDO:0008199"]));
    expect(m.nodes.some((n) => n.node.type === "phenotype")).toBe(false);
    expect(m.nodes.length).toBeLessThanOrEqual(MAX_MAP_NODES);
    expect(m.edges.length).toBeLessThanOrEqual(MAX_MAP_EDGES);
    expect(m.contradiction_edge_ids.length).toBeGreaterThan(0);
  });

  it("includes and flags contradictions", async () => {
    const m = await map({ center: PD24 });
    const contradicts = m.edges.find((e) => e.relation === "contradicts");
    expect(contradicts).toBeDefined();
    expect(m.contradiction_edge_ids).toContain(contradicts!.id);
    expect(isContradiction(contradicts!)).toBe(true);
  });

  it("pulls the contradicting publication onto the PSAP map", async () => {
    const m = await map({ center: PSAP });
    expect(ids(m)).toContain("PMID:33793763");
  });

  it("filters relations and confidence, and caps the size", async () => {
    const m = await map({ center: GAUCHER_3, relations: ["caused_by"] });
    expect(m.edges.every((e) => e.relation === "caused_by")).toBe(true);
    const strict = await map({ center: GAUCHER_3, minConfidence: 0.8 });
    expect(strict.edges.every((e) => e.confidence >= 0.8)).toBe(true);
    const tiny = await map({ center: GAUCHER_3, limit: 2 });
    expect(tiny.nodes).toHaveLength(2);
    expect(tiny.truncated.nodes_hidden).toBeGreaterThan(0);
  });

  it("returns null for an unknown center", async () => {
    expect(await mockClient.getGraph({ center: "MONDO:0000000" })).toBeNull();
  });

  it("is deterministic", async () => {
    expect(await map({ center: GBA1, depth: 2 })).toEqual(await map({ center: GBA1, depth: 2 }));
  });
});

describe("merging expanded neighbourhoods", () => {
  it("adds the expanded node's neighbours and keeps highlighted edges", async () => {
    const base = await map({ center: GAUCHER_2 });
    const extra = await map({ center: "MONDO:0008199" });
    const highlight = new Set([extra.edges[0]!.id]);
    const merged = mergeMaps(base, [extra], highlight);
    expect(ids(merged)).toEqual(expect.arrayContaining(ids(extra)));
    expect(merged.edges.map((e) => e.id)).toContain(extra.edges[0]!.id);
    expect(merged.legend.node_types.disease).toBeGreaterThan(1);
    expect(mergeMaps(base, [])).toBe(base);
  });
});

describe("map URLs", () => {
  it("encodes ids", () => {
    expect(mapHref()).toBe("/map");
    expect(mapHref({ center: GAUCHER_2 })).toBe("/map?center=MONDO%3A0009266");
    expect(
      mapHref({
        center: GAUCHER_2,
        depth: 2,
        phenotypes: true,
        expand: [GBA1],
        highlight: ["E:1"],
      }),
    ).toBe("/map?center=MONDO%3A0009266&depth=2&phenotypes=1&expand=HGNC%3A4177&highlight=E%3A1");
  });

  it("validates params and drops anything malformed", () => {
    const state = parseMapParams({
      center: GAUCHER_2,
      depth: "2",
      phenotypes: "1",
      expand: `${GBA1},<script>,${GAUCHER_2},${GBA1}`,
      highlight: "E:61528699fb974eda,E:bad",
    });
    expect(state).toEqual({
      center: GAUCHER_2,
      depth: 2,
      phenotypes: true,
      expand: [GBA1],
      highlight: ["E:61528699fb974eda"],
    });
    expect(parseMapParams({ center: "nope", depth: "9" }).center).toBeNull();
    expect(parseMapParams({ depth: "9" }).depth).toBe(1);
    const many = Array.from({ length: 20 }, (_, i) => `HGNC:${i}`).join(",");
    expect(parseMapParams({ expand: many }).expand).toHaveLength(MAX_EXPAND);
  });
});

describe("layout and labels", () => {
  it("lays out deterministically within the tick cap", async () => {
    const m = await map();
    const a = computeLayout(m.nodes, m.edges, null);
    const b = computeLayout(m.nodes, m.edges, null);
    expect([...a.positions]).toEqual([...b.positions]);
    expect(a.ticks).toBeLessThanOrEqual(MAX_TICKS);
    const centred = computeLayout((await map({ center: GBA1 })).nodes, [], GBA1);
    expect(centred.positions.get(GBA1)).toEqual({ x: 0, y: 0 });
    expect(computeLayout([], [], null).bounds).toEqual([0, 0, 0, 0]);
  });

  it("never lets two labels overlap", () => {
    const candidates = Array.from({ length: 12 }, (_, i) => ({
      id: `N:${i}`,
      text: "a fairly long node label",
      x: 100 + (i % 3) * 20,
      y: 100 + Math.floor(i / 3) * 10,
      r: 8,
      forced: false,
      priority: i,
    }));
    const placed = placeLabels(candidates);
    expect(placed.size).toBeGreaterThan(0);
    expect(placed.size).toBeLessThan(candidates.length);
    const boxes = [...placed].map(([id, p]) =>
      labelBox(
        candidates.find((c) => c.id === id)!,
        p.spot,
      ),
    );
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const [a, b] = [boxes[i]!, boxes[j]!];
        expect(a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3]).toBe(false);
      }
    }
    const forced = placeLabels([
      { ...candidates[0]!, forced: true },
      { ...candidates[0]!, id: "X:1", forced: true },
    ]);
    expect(forced.size).toBe(2);
  });
});

describe("http client /graph", () => {
  it("builds the query string", () => {
    expect(graphQueryString({})).toBe("");
    expect(
      graphQueryString({
        center: GAUCHER_2,
        depth: 2,
        types: ["gene", "disease"],
        relations: ["caused_by"],
        minConfidence: 0.5,
        limit: 40,
      }),
    ).toBe(
      "?center=MONDO%3A0009266&depth=2&types=gene%2Cdisease&relations=caused_by&min_confidence=0.5&limit=40",
    );
  });

  it("validates the response, maps 404 to null and falls back on failure", async () => {
    const body = JSON.parse(JSON.stringify(await map({ center: GAUCHER_2 })));
    const fetchOk = vi.fn().mockResolvedValue(jsonResponse(body));
    const http = createHttpClient("http://atlas.test", { fetchImpl: fetchOk });
    expect((await http.getGraph({ center: GAUCHER_2 }))?.center).toBe(GAUCHER_2);
    expect(fetchOk.mock.calls[0]![0]).toBe("http://atlas.test/api/v1/graph?center=MONDO%3A0009266");

    const missing = createHttpClient("http://atlas.test", {
      fetchImpl: vi.fn().mockResolvedValue(jsonResponse({ detail: "unknown" }, 404)),
    });
    expect(await missing.getGraph({ center: "MONDO:0000000" })).toBeNull();

    const down = createFallbackClient(
      createHttpClient("http://atlas.test", {
        fetchImpl: vi.fn().mockRejectedValue(new TypeError("fetch failed")),
      }),
      mockClient,
    );
    expect((await down.getGraph({ center: GAUCHER_2 }))?.center).toBe(GAUCHER_2);
    expect(down.usedFallback).toBe(true);
  });
});

describe("placeLabels obstacles and hubs", () => {
  const cand = (id: string, x: number, y: number, priority = 1, forced = false) => ({
    id,
    text: "Label",
    x,
    y,
    r: 6,
    forced,
    priority,
  });

  it("never places a label on top of an edge badge", () => {
    const obstacle: [number, number, number, number] = [-40, 0, 40, 30];
    const shown = placeLabels([cand("a", 0, 0)], [obstacle]);
    expect(shown.get("a")?.spot).not.toBe("below");
  });

  it("does not let a busy hub label cover another node", () => {
    const shown = placeLabels([cand("hub", 0, 0, 50), cand("other", 0, 20, 1)]);
    expect(shown.get("hub")?.spot).not.toBe("below");
  });

  it("always labels forced nodes", () => {
    const blockAll: [number, number, number, number] = [-200, -200, 200, 200];
    expect(placeLabels([cand("c", 0, 0, 1, true)], [blockAll]).has("c")).toBe(true);
  });
});

describe("placeLabels bounds", () => {
  it("keeps labels inside the canvas, choosing another side near the edge", () => {
    const c = {
      id: "edge",
      text: "A long label near the edge",
      x: 195,
      y: 50,
      r: 6,
      forced: false,
      priority: 1,
    };
    const shown = placeLabels([c], [], [0, 0, 200, 200]);
    expect(shown.has("edge") ? shown.get("edge")?.spot : "hidden").not.toBe("right");
  });
});
