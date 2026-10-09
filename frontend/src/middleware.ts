import { NextResponse, type NextRequest } from "next/server";
import { CSP_HEADER, NONCE_HEADER, buildCsp, createNonce, originOf } from "@/lib/security-headers";

/**
 * Per-request Content-Security-Policy with a fresh script nonce. Next.js reads the policy from the
 * request headers and adds the nonce to its own inline scripts; the root layout reads the nonce,
 * which keeps every page dynamically rendered (a prerendered page could not carry one).
 */
export function middleware(request: NextRequest) {
  const nonce = createNonce();
  const csp = buildCsp({
    nonce,
    apiOrigin: originOf(process.env.NEXT_PUBLIC_API_URL),
    isDev: process.env.NODE_ENV === "development",
  });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(NONCE_HEADER, nonce);
  requestHeaders.set(CSP_HEADER, csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set(CSP_HEADER, csp);
  return response;
}

export const config = {
  matcher: [
    {
      // Pages and server actions only: static files, images and route handlers need no nonce.
      source: "/((?!api|_next/static|_next/image|favicon.ico|robots.txt).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
