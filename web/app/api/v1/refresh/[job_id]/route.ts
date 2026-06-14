/**
 * Server-side proxy for GET /api/v1/refresh/{job_id}.
 *
 * Browser clients poll this same-origin endpoint to track refresh job
 * progress. Next.js runs this handler server-side on the Pi and forwards
 * the request to FastAPI on 127.0.0.1:8000.
 */
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://127.0.0.1:8000";

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ job_id: string }> }
) {
  try {
    const { job_id } = await context.params;
    const upstream = await fetch(`${API_BASE}/api/v1/refresh/${job_id}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    console.error("[refresh/{job_id} proxy] upstream error:", err);
    return NextResponse.json(
      { error: "Failed to reach FastAPI backend" },
      { status: 502 }
    );
  }
}
