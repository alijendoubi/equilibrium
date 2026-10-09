/**
 * Security headers. The Content-Security-Policy is built per request in src/middleware.ts so
 * Next.js can stamp its inline scripts with a fresh nonce; the static headers apply to every
 * response through next.config.ts.
 */

export const NONCE_HEADER = "x-nonce";
export const CSP_HEADER = "Content-Security-Policy";

export interface CspOptions {
  nonce: string;
  /** Origin the browser may call directly (ExplainPanel posts to the Atlas API). */
  apiOrigin: string | null;
  /** Dev needs 'unsafe-eval' for React Refresh; production never gets it. */
  isDev: boolean;
}

/** Origin of an absolute http(s) URL, or null for anything else. */
export function originOf(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.origin : null;
  } catch {
    return null;
  }
}

export function buildCsp({ nonce, apiOrigin, isDev }: CspOptions): string {
  const scriptSrc = ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'"];
  if (isDev) scriptSrc.push("'unsafe-eval'");
  const connectSrc = ["'self'", ...(apiOrigin ? [apiOrigin] : [])];
  if (isDev) connectSrc.push("ws:");
  const directives: [string, string[]][] = [
    ["default-src", ["'self'"]],
    ["script-src", scriptSrc],
    // Inline style attributes (map positions, swatches) cannot carry a nonce.
    ["style-src", ["'self'", "'unsafe-inline'"]],
    ["img-src", ["'self'", "data:", "blob:"]],
    ["font-src", ["'self'"]],
    ["connect-src", connectSrc],
    ["object-src", ["'none'"]],
    ["base-uri", ["'self'"]],
    ["form-action", ["'self'"]],
    ["frame-ancestors", ["'none'"]],
  ];
  const policy = directives.map(([name, values]) => `${name} ${values.join(" ")}`);
  if (!isDev) policy.push("upgrade-insecure-requests");
  return policy.join("; ");
}

/** A base64 nonce from 16 random bytes (Web Crypto, so it works in the edge runtime). */
export function createNonce(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return btoa(String.fromCharCode(...bytes));
}

const TWO_YEARS_S = 63_072_000;

/** Headers that do not depend on the request; applied to every route in next.config.ts. */
export const STATIC_SECURITY_HEADERS: { key: string; value: string }[] = [
  { key: "Strict-Transport-Security", value: `max-age=${TWO_YEARS_S}; includeSubDomains` },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];
