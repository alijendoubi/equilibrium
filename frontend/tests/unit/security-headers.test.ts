// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  CSP_HEADER,
  NONCE_HEADER,
  STATIC_SECURITY_HEADERS,
  buildCsp,
  createNonce,
  originOf,
} from "@/lib/security-headers";
import { middleware } from "@/middleware";

const directive = (csp: string, name: string) =>
  csp
    .split("; ")
    .find((d) => d.startsWith(`${name} `))
    ?.split(" ")
    .slice(1) ?? [];

describe("buildCsp", () => {
  const prod = buildCsp({ nonce: "abc", apiOrigin: "https://api.example.org", isDev: false });

  it("allows scripts only by nonce in production, never eval or inline", () => {
    const scripts = directive(prod, "script-src");
    expect(scripts).toContain("'nonce-abc'");
    expect(scripts).not.toContain("'unsafe-eval'");
    expect(scripts).not.toContain("'unsafe-inline'");
  });

  it("lets the browser reach the API origin and nothing else", () => {
    expect(directive(prod, "connect-src")).toEqual(["'self'", "https://api.example.org"]);
  });

  it("forbids framing, plugins and foreign form targets", () => {
    expect(directive(prod, "frame-ancestors")).toEqual(["'none'"]);
    expect(directive(prod, "object-src")).toEqual(["'none'"]);
    expect(directive(prod, "form-action")).toEqual(["'self'"]);
    expect(prod).toContain("upgrade-insecure-requests");
  });

  it("adds eval and websockets only in development", () => {
    const dev = buildCsp({ nonce: "abc", apiOrigin: null, isDev: true });
    expect(directive(dev, "script-src")).toContain("'unsafe-eval'");
    expect(directive(dev, "connect-src")).toEqual(["'self'", "ws:"]);
    expect(dev).not.toContain("upgrade-insecure-requests");
  });
});

describe("helpers", () => {
  it("extracts http(s) origins and rejects everything else", () => {
    expect(originOf("https://api.example.org/v1/x")).toBe("https://api.example.org");
    expect(originOf("http://localhost:8000")).toBe("http://localhost:8000");
    expect(originOf("javascript:alert(1)")).toBeNull();
    expect(originOf("not a url")).toBeNull();
    expect(originOf(undefined)).toBeNull();
  });

  it("creates distinct base64 nonces of 16 bytes", () => {
    const a = createNonce();
    expect(a).toMatch(/^[A-Za-z0-9+/]{22}==$/);
    expect(createNonce()).not.toBe(a);
  });

  it("sets HSTS, nosniff, DENY framing and a restrictive permissions policy", () => {
    const keys = Object.fromEntries(STATIC_SECURITY_HEADERS.map((h) => [h.key, h.value]));
    expect(keys["Strict-Transport-Security"]).toMatch(/max-age=\d+; includeSubDomains/);
    expect(keys["X-Content-Type-Options"]).toBe("nosniff");
    expect(keys["X-Frame-Options"]).toBe("DENY");
    expect(keys["Permissions-Policy"]).toContain("camera=()");
  });
});

describe("middleware", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("puts a fresh nonce in the response CSP and forwards it to the page", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.org");
    const first = middleware(new NextRequest("https://atlas.example.org/map"));
    const second = middleware(new NextRequest("https://atlas.example.org/map"));
    const csp = first.headers.get(CSP_HEADER) ?? "";

    const nonce = /'nonce-([^']+)'/.exec(csp)?.[1];
    expect(nonce).toBeTruthy();
    expect(first.headers.get(`x-middleware-request-${NONCE_HEADER}`)).toBe(nonce);
    expect(directive(csp, "connect-src")).toContain("https://api.example.org");
    expect(second.headers.get(CSP_HEADER)).not.toBe(csp);
  });
});
