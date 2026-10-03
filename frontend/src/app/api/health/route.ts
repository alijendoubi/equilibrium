import { NextResponse } from "next/server";
import { checkBackend, type HealthResponse } from "@/lib/health";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse<HealthResponse>> {
  const backend = await checkBackend();
  return NextResponse.json({ status: "ok", backend }, { headers: { "Cache-Control": "no-store" } });
}
