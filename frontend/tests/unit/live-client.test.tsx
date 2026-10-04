import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SearchPage from "@/app/search/page";
import { FALLBACK_NOTICE } from "@/components/MockBanner";
import { createFallbackClient, createHttpClient, mockClient } from "@/lib/api/client";
import { actionsHref, nodeHref } from "@/lib/format";

const BASE = "http://atlas.test";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function live(fetchImpl: typeof fetch, timeoutMs = 4000) {
  return createFallbackClient(
    createHttpClient(BASE, { fetchImpl, timeoutMs, explainTimeoutMs: timeoutMs }),
    mockClient,
  );
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("live client with demo fallback", () => {
  it("falls back to demo data when the backend is down", async () => {
    const client = live(vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    const res = await client.search("Gaucher");
    expect(res.results.length).toBeGreaterThan(0);
    expect(client.usedFallback).toBe(true);
  });

  it("falls back on a 5xx answer", async () => {
    const client = live(vi.fn().mockResolvedValue(jsonResponse({ detail: "boom" }, 503)));
    const node = await client.getNode("MONDO:0009266");
    expect(node?.node.label).toBe("Gaucher disease type II");
    expect(client.usedFallback).toBe(true);
  });

  it("falls back when the backend does not answer in time", async () => {
    const hang: typeof fetch = (_url, init) =>
      new Promise((_, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason));
      });
    const client = live(hang, 20);
    const res = await client.explain(["E:61528699fb974eda"], "family");
    expect(res.source).toBe("template");
    expect(client.usedFallback).toBe(true);
  });

  it("treats a 404 as a real answer, not a failure", async () => {
    const client = live(vi.fn().mockResolvedValue(jsonResponse({ detail: "not found" }, 404)));
    expect(await client.getNode("MONDO:0009266")).toBeNull();
    expect(client.usedFallback).toBe(false);
  });

  it("uses the live answer when it is valid", async () => {
    const body = { query: "x", results: [], searched: ["live index"] };
    const client = live(vi.fn().mockResolvedValue(jsonResponse(body)));
    expect((await client.search("x")).searched).toEqual(["live index"]);
    expect(client.usedFallback).toBe(false);
  });
});

describe("encoded ids", () => {
  it("URL-encodes the ':' in CURIEs for every GET", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({}, 404));
    const http = createHttpClient(BASE, { fetchImpl });
    await http.getNode("MONDO:0009266");
    await http.getActions("MONDO:0012517");
    await http.getCoverage("MONDO:0012517");
    await http.getPath("MONDO:0009266", "clinicaltrials:NCT05778617").catch(() => undefined);
    const urls = fetchImpl.mock.calls.map((c) => String(c[0]));
    expect(urls).toEqual([
      `${BASE}/api/v1/nodes/MONDO%3A0009266`,
      `${BASE}/api/v1/actions/MONDO%3A0012517`,
      `${BASE}/api/v1/coverage/MONDO%3A0012517`,
      `${BASE}/api/v1/paths?from=MONDO%3A0009266&to=clinicaltrials%3ANCT05778617&k=3`,
    ]);
  });

  it("POSTs explain with edge ids and audience as JSON", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse({
        steps: [{ text: "t", edge_ids: ["E:61528699fb974eda"], is_hypothesis: false }],
        summary: "s",
        caveats: [],
        source: "cache",
        model: "gpt-5-mini",
        prompt_version: "v1",
        ai_generated: true,
      }),
    );
    const res = await createHttpClient(BASE, { fetchImpl }).explain(
      ["E:61528699fb974eda"],
      "researcher",
    );
    expect(res.model).toBe("gpt-5-mini");
    const [url, init] = fetchImpl.mock.calls[0]!;
    expect(url).toBe(`${BASE}/api/v1/explain`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      edge_ids: ["E:61528699fb974eda"],
      audience: "researcher",
    });
  });

  it("builds encoded page links", () => {
    expect(nodeHref("MONDO:0012517")).toBe("/disease/MONDO%3A0012517");
    expect(actionsHref("MONDO:0009266")).toBe("/actions/MONDO%3A0009266");
  });
});

describe("fallback notice on pages", () => {
  it("shows 'Showing cached demo data' when the live API fails", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCKS", "false");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    render(await SearchPage({ searchParams: Promise.resolve({ q: "Gaucher" }) }));
    expect(screen.getByRole("status")).toHaveTextContent(FALLBACK_NOTICE);
    expect(screen.getByText("Gaucher disease type II")).toBeInTheDocument();
    expect(screen.queryByText(/Mock data\./)).toBeNull();
  });
});
