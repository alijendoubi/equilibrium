import { describe, expect, it } from "vitest";
import { mockClient } from "@/lib/api/client";
import { explanationToText } from "@/lib/api/explain-template";
import { explainRequestSchema, explainResponseSchema } from "@/lib/api/schemas";

const GOLDEN_EDGES = [
  "E:61528699fb974eda", // Gaucher type II caused by GBA1
  "E:0123bcf2d717e9f0", // GBA1 takes part in lysosomal dysfunction
  "E:36c6e1a96c92e376", // Parkinson's has mechanism lysosomal dysfunction (inferred)
  "E:ee3efd9484282caf", // ASPro-PD studies Parkinson's
];

const VALID_RESPONSE = {
  steps: [{ text: "Gaucher type II is caused by GBA1.", edge_ids: ["E:61528699fb974eda"] }],
  summary: "One link.",
  caveats: [],
  source: "live",
  model: "gpt-5-mini",
  prompt_version: "explain-v1",
  ai_generated: true,
};

describe("explain schemas", () => {
  it("parses a backend response and defaults is_hypothesis to false", () => {
    const parsed = explainResponseSchema.parse(VALID_RESPONSE);
    expect(parsed.steps[0]?.is_hypothesis).toBe(false);
    expect(parsed.ai_generated).toBe(true);
  });

  it("rejects a step that cites no edge", () => {
    const bad = { ...VALID_RESPONSE, steps: [{ text: "Uncited claim.", edge_ids: [] }] };
    expect(explainResponseSchema.safeParse(bad).success).toBe(false);
  });

  it("rejects an unknown source", () => {
    expect(explainResponseSchema.safeParse({ ...VALID_RESPONSE, source: "guess" }).success).toBe(
      false,
    );
  });

  it("limits a request to 1..12 edges and a known audience", () => {
    const ids = (n: number) =>
      Array.from({ length: n }, (_, i) => `E:${String(i).padStart(16, "0")}`);
    expect(explainRequestSchema.safeParse({ edge_ids: ids(12), audience: "family" }).success).toBe(
      true,
    );
    expect(explainRequestSchema.safeParse({ edge_ids: ids(13), audience: "family" }).success).toBe(
      false,
    );
    expect(explainRequestSchema.safeParse({ edge_ids: [], audience: "family" }).success).toBe(
      false,
    );
    expect(explainRequestSchema.safeParse({ edge_ids: ids(1), audience: "kids" }).success).toBe(
      false,
    );
  });
});

describe("mock explain", () => {
  it("returns template steps, one per edge, with hypotheses flagged", async () => {
    const res = await mockClient.explain(GOLDEN_EDGES, "family");
    expect(explainResponseSchema.safeParse(res).success).toBe(true);
    expect(res.source).toBe("template");
    expect(res.ai_generated).toBe(false);
    expect(res.model).toBeNull();
    expect(res.steps.map((s) => s.edge_ids[0])).toEqual(GOLDEN_EDGES);
    expect(res.steps.map((s) => s.is_hypothesis)).toEqual([false, false, true, false]);
    expect(res.steps[0]?.text).toContain("Gaucher disease type II caused by GBA1");
    expect(res.caveats.join(" ")).toMatch(/hypothesis/);
  });

  it("is deterministic and adds sources for researchers", async () => {
    const a = await mockClient.explain(GOLDEN_EDGES, "researcher");
    const b = await mockClient.explain(GOLDEN_EDGES, "researcher");
    expect(a).toEqual(b);
    expect(a.steps[0]?.text).toMatch(/Source: omim OMIM:230900/);
  });

  it("rejects when no edge is known", async () => {
    await expect(mockClient.explain(["E:ffffffffffffffff"], "family")).rejects.toThrow(
      /in the demo data/,
    );
  });

  it("turns an explanation into copyable text with its label", async () => {
    const res = await mockClient.explain(GOLDEN_EDGES.slice(0, 1), "family");
    const text = explanationToText("Brief", res);
    expect(text.split("\n")[0]).toBe("Brief");
    expect(text).toContain("(evidence: E:61528699fb974eda)");
    expect(text).toContain("Template text (AI unavailable)");
  });
});

describe("golden flow mocks", () => {
  it("routes Gaucher type II to ASPro-PD and Cure Parkinson's with snapshot ids", async () => {
    const toTrial = await mockClient.getPath("MONDO:0009266", "clinicaltrials:NCT05778617");
    expect(toTrial.paths[0]?.nodes.map((n) => n.id)).toEqual([
      "MONDO:0009266",
      "HGNC:4177",
      "MONDO:0008199",
      "clinicaltrials:NCT05778617",
    ]);
    const toFunder = await mockClient.getPath("MONDO:0009266", "org:cure-parkinsons");
    expect(toFunder.paths[0]?.nodes.at(-1)?.type).toBe("funder");
    const gap = await mockClient.getActions("MONDO:0012517");
    expect(gap?.coverage?.result).toBe("no_supported_route");
    expect((await mockClient.getNode("HGNC:9498"))?.node.label).toBe("PSAP");
  });
});
