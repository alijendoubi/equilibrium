import { getServerEnv } from "@/lib/env";

export const BACKEND_TIMEOUT_MS = 2000;

export type BackendStatus = "ok" | "unreachable";

export interface HealthResponse {
  status: "ok";
  backend: BackendStatus;
}

/** Probes `${BACKEND_URL}/health` with a timeout. Never throws. */
export async function checkBackend(timeoutMs: number = BACKEND_TIMEOUT_MS): Promise<BackendStatus> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const { BACKEND_URL } = getServerEnv();
    const res = await fetch(`${BACKEND_URL}/health`, {
      signal: controller.signal,
      cache: "no-store",
    });
    return res.ok ? "ok" : "unreachable";
  } catch {
    // Network error, timeout (abort) or invalid env: report as unreachable.
    return "unreachable";
  } finally {
    clearTimeout(timer);
  }
}
