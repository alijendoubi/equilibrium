import { NextRequest, NextResponse } from "next/server";

const STATIC_FILE = /\.(?:css|js|map|png|jpg|jpeg|gif|svg|ico|webp|woff2?)$/i;

/**
 * Serves the public-facing site from a marketing subdomain while preserving the Atlas app on the
 * primary host. Configure MARKETING_HOST=home.yourdomain.com in production. Without it, any
 * `home.` subdomain is treated as the marketing host, which makes local `home.localhost` testing easy.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname.startsWith("/_next") || pathname.startsWith("/api") || STATIC_FILE.test(pathname)) {
    return NextResponse.next();
  }

  const host = request.headers.get("host")?.split(":")[0]?.toLowerCase() ?? "";
  const configuredHost = process.env.MARKETING_HOST?.trim().toLowerCase();
  const isMarketingHost = configuredHost ? host === configuredHost : host.startsWith("home.");
  if (!isMarketingHost || pathname === "/home") return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = "/home";
  return NextResponse.rewrite(url);
}

export const config = { matcher: "/:path*" };
