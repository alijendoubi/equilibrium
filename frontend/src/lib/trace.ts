"use server";

import { getServerAtlasClient } from "@/lib/api/server-client";
import { CURIE_PATTERN } from "@/lib/api/schemas";
import {
  MAX_ALTERNATIVES,
  normalizeQuery,
  type GraphResult,
  type TraceResult,
} from "@/lib/trace-result";

const UNREACHABLE = "The atlas could not be reached. Try again in a moment.";
const MAX_ID_LENGTH = 200;

/**
 * Home page "Trace it": search the atlas, then load the direct (depth-1) evidence map of the best
 * match. Input comes from the browser, so it is re-validated here.
 */
export async function traceQuery(raw: unknown): Promise<TraceResult> {
  const query = normalizeQuery(raw);
  if (!query) {
    return { status: "invalid", query, message: "Type a disease, gene or symptom first." };
  }
  try {
    const client = await getServerAtlasClient();
    const search = await client.search(query);
    const [match, ...rest] = search.results;
    if (!match) {
      return {
        status: "not_found",
        query,
        searched: search.searched,
        isMock: client.isMock,
        usedFallback: client.usedFallback,
      };
    }
    const graph = await client.getGraph({ center: match.node.id, depth: 1 });
    return {
      status: "found",
      query,
      match,
      alternatives: rest.slice(0, MAX_ALTERNATIVES),
      graph,
      isMock: client.isMock,
      usedFallback: client.usedFallback,
    };
  } catch (error) {
    console.error("traceQuery failed", { query, error });
    return { status: "error", query, message: UNREACHABLE };
  }
}

/** Re-centres the traced map on another search hit ("Not what you meant?"). */
export async function traceNode(rawId: unknown): Promise<GraphResult> {
  const id = typeof rawId === "string" ? rawId.trim() : "";
  if (!id || id.length > MAX_ID_LENGTH || !CURIE_PATTERN.test(id)) {
    return { status: "error", message: "That is not an atlas id." };
  }
  try {
    const client = await getServerAtlasClient();
    const graph = await client.getGraph({ center: id, depth: 1 });
    return { status: "ok", graph, isMock: client.isMock, usedFallback: client.usedFallback };
  } catch (error) {
    console.error("traceNode failed", { id, error });
    return { status: "error", message: UNREACHABLE };
  }
}
