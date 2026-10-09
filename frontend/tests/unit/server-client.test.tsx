// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const requestHeaders = vi.hoisted(() => ({ current: new Headers() }));
vi.mock("next/headers", () => ({ headers: async () => requestHeaders.current }));

import ClustersPage from "@/app/clusters/page";
import { createHttpClient, getAtlasClient } from "@/lib/api/client";
import {
  FRONTEND_TOKEN_HEADER,
  VISITOR_IP_HEADER,
  getServerAtlasClient,
  visitorHeaders,
} from "@/lib/api/server-client";
import { traceQuery } from "@/lib/trace";

const read = (values: Record<string, string>) => (name: string) => values[name] ?? null;

describe("visitorHeaders", () => {
  it("sends the token and the trusted visitor IP together", () => {
    expect(visitorHeaders("tok", read({ "x-real-ip": "203.0.113.7" }))).toEqual({
      [FRONTEND_TOKEN_HEADER]: "tok",
      [VISITOR_IP_HEADER]: "203.0.113.7",
    });
    expect(visitorHeaders("tok", read({ "x-real-ip": "2001:db8::1" }))[VISITOR_IP_HEADER]).toBe(
      "2001:db8::1",
    );
  });

  it("sends nothing without a token, or without a valid trusted IP", () => {
    expect(visitorHeaders(undefined, read({ "x-real-ip": "203.0.113.7" }))).toEqual({});
    expect(visitorHeaders("  ", read({ "x-real-ip": "203.0.113.7" }))).toEqual({});
    expect(visitorHeaders("tok", read({ "x-real-ip": "not-an-ip" }))).toEqual({});
    expect(visitorHeaders("tok", read({}))).toEqual({});
  });

  it("never trusts a client-supplied X-Forwarded-For", () => {
    expect(visitorHeaders("tok", read({ "x-forwarded-for": "6.6.6.6" }))).toEqual({});
  });
});

/** A fetch that records request headers and answers like the API would for each route. */
function recordingFetch() {
  const seen: Headers[] = [];
  const body = (url: string) => {
    if (url.includes("/search")) return { query: "GBA1", results: [], searched: ["test"] };
    if (url.includes("/clusters")) return { clusters: [], method: null };
    return {};
  };
  const impl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    seen.push(new Headers(init?.headers));
    return new Response(JSON.stringify(body(String(input))), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  });
  return { impl, seen };
}

describe("live mode", () => {
  let fetchSpy: ReturnType<typeof recordingFetch>;

  beforeEach(() => {
    fetchSpy = recordingFetch();
    vi.stubGlobal("fetch", fetchSpy.impl);
    vi.stubEnv("NEXT_PUBLIC_USE_MOCKS", "false");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    vi.stubEnv("FRONTEND_API_TOKEN", "server-secret");
    requestHeaders.current = new Headers({ "x-real-ip": "203.0.113.7" });
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("the HTTP client adds configured headers to every request", async () => {
    const client = createHttpClient("http://api.test", {
      fetchImpl: fetchSpy.impl,
      headers: { [FRONTEND_TOKEN_HEADER]: "x" },
    });
    await client.search("GBA1");
    expect(fetchSpy.seen[0]?.get(FRONTEND_TOKEN_HEADER)).toBe("x");
  });

  it("the trace server action forwards the token and visitor IP", async () => {
    await traceQuery("GBA1");
    expect(fetchSpy.seen.length).toBeGreaterThan(0);
    for (const h of fetchSpy.seen) {
      expect(h.get(FRONTEND_TOKEN_HEADER)).toBe("server-secret");
      expect(h.get(VISITOR_IP_HEADER)).toBe("203.0.113.7");
    }
  });

  it("server components forward them too", async () => {
    await ClustersPage();
    expect(fetchSpy.seen[0]?.get(VISITOR_IP_HEADER)).toBe("203.0.113.7");
  });

  it("the browser client never sends the token, even when the server has it", async () => {
    await getAtlasClient().search("GBA1");
    expect(fetchSpy.seen[0]?.get(FRONTEND_TOKEN_HEADER)).toBeNull();
    expect(fetchSpy.seen[0]?.get(VISITOR_IP_HEADER)).toBeNull();
  });

  it("without a token the server client sends nothing extra", async () => {
    vi.stubEnv("FRONTEND_API_TOKEN", "");
    await (await getServerAtlasClient()).search("GBA1");
    expect(fetchSpy.seen[0]?.get(FRONTEND_TOKEN_HEADER)).toBeNull();
  });
});
