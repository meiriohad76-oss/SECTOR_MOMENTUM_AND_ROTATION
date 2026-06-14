/**
 * Server-side proxy for POST /api/v1/refresh.
 *
 * Browser clients (which may not have direct access to the FastAPI server)
 * call this same-origin endpoint. Next.js runs this handler server-side on
 * the Pi and forwards the request to FastAPI on 127.0.0.1:8000.
 */
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json().catch(() => ({}));
    const upstream = await fetch(`${API_BASE}/api/v1/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    console.error("[refresh proxy] upstream error:", err);
    return NextResponse.json(
      { error: "Failed to reach FastAPI backend" },
      { status: 502 }
    );
  }
}
