// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "@/app/api/health/route";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.useRealTimers();
});

describe("GET /api/health", () => {
  it("reports backend ok when the backend health check succeeds", async () => {
    vi.stubEnv("BACKEND_URL", "http://backend:8000");
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const res = await GET();

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok", backend: "ok" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://backend:8000/health",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("reports backend unreachable when fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));

    const res = await GET();

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok", backend: "unreachable" });
  });

  it("reports backend unreachable on a non-2xx response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 503 })));

    const res = await GET();

    expect(await res.json()).toEqual({ status: "ok", backend: "unreachable" });
  });

  it("reports backend unreachable when the request times out", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () =>
              reject(new DOMException("aborted", "AbortError")),
            );
          }),
      ),
    );

    const pending = GET();
    await vi.advanceTimersByTimeAsync(2000);
    const res = await pending;
    vi.useRealTimers();

    expect(await res.json()).toEqual({ status: "ok", backend: "unreachable" });
  });
});
