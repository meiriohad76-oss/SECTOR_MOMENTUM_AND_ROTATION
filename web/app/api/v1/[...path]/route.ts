/**
 * Catch-all proxy for /api/v1/* → FastAPI backend.
 *
 * Next.js 15 App Router owns the entire /api/v1/ namespace once any Route Handler
 * exists under that prefix — next.config.mjs rewrites are never reached for those
 * paths. This catch-all forwards every unmatched request to FastAPI so browser
 * clients (which cannot reach 127.0.0.1:8001 directly) get the same-origin response.
 *
 * Specific Route Handlers (refresh, refresh/[job_id], universe/analyze) take
 * priority over this catch-all per Next.js route-precedence rules.
 */
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://127.0.0.1:8001";

async function proxy(
  request: NextRequest,
  path: string[],
): Promise<NextResponse> {
  const url = new URL(request.url);
  const upstream = `${API_BASE}/api/v1/${path.join("/")}${url.search}`;

  const isReadMethod = request.method === "GET" || request.method === "HEAD";
  const body = isReadMethod ? undefined : await request.text();

  const upstreamHeaders: HeadersInit = { Accept: "application/json" };
  if (!isReadMethod) upstreamHeaders["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(upstream, {
      method: request.method,
      headers: upstreamHeaders,
      body,
      // @ts-expect-error — Node fetch supports duplex for streaming bodies
      duplex: "half",
    });
  } catch (err) {
    console.error(`[api-proxy] upstream unreachable: ${upstream}`, err);
    return NextResponse.json(
      { error: "FastAPI backend unreachable", upstream },
      { status: 502 },
    );
  }

  const contentType = res.headers.get("content-type") ?? "application/json";

  // Stream Server-Sent Events through without buffering
  if (contentType.includes("text/event-stream") && res.body) {
    return new NextResponse(res.body, {
      status: res.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }

  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": contentType },
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(request, path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(request, path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(request, path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(request, path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(request, path);
}
