import { isIP } from "node:net";
import { headers } from "next/headers";
import { getAtlasClient, shouldUseMocks, type AtlasClient } from "@/lib/api/client";

/**
 * Server-only Atlas client (server components and server actions, never the browser). When
 * FRONTEND_API_TOKEN is set it vouches for the visitor's IP, so the API rate-limits each visitor
 * instead of putting every user behind Vercel's shared egress address into one bucket (#82).
 */

export const FRONTEND_TOKEN_HEADER = "X-Atlas-Frontend";
export const VISITOR_IP_HEADER = "X-Atlas-Visitor-IP";

/**
 * Vercel's edge sets x-real-ip to the connecting client and overwrites any value the client sent,
 * so it is the only request header trusted here. Deploy elsewhere only behind a proxy that does
 * the same, or leave FRONTEND_API_TOKEN unset.
 */
export const TRUSTED_CLIENT_IP_HEADER = "x-real-ip";

/** Headers proving the request comes from our server, or none when they cannot be trusted. */
export function visitorHeaders(
  token: string | undefined,
  readHeader: (name: string) => string | null,
): Record<string, string> {
  const secret = token?.trim();
  const ip = readHeader(TRUSTED_CLIENT_IP_HEADER)?.trim() ?? "";
  if (!secret || isIP(ip) === 0) return {};
  return { [FRONTEND_TOKEN_HEADER]: secret, [VISITOR_IP_HEADER]: ip };
}

export async function getServerAtlasClient(): Promise<AtlasClient> {
  const token = process.env.FRONTEND_API_TOKEN;
  // No token (local, mocks): skip headers() so pages stay statically renderable.
  if (!token?.trim() || shouldUseMocks()) return getAtlasClient();
  const requestHeaders = await headers();
  return getAtlasClient(visitorHeaders(token, (name) => requestHeaders.get(name)));
}
