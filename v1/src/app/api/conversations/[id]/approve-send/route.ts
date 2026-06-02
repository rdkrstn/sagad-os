import { NextRequest, NextResponse } from "next/server";

interface ApprovalProxyRequest {
  approved?: boolean;
  supervisor_id?: string;
  edited_reply?: string | null;
}

function agentStudioBaseUrl(): string | null {
  const value = process.env.SAGAD_API_BASE_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

function jsonResponse(payload: unknown, status: number): NextResponse {
  return NextResponse.json(payload, { status });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return jsonResponse(
      { detail: "SAGAD_API_BASE_URL is not configured." },
      503,
    );
  }

  const { id } = await context.params;
  const payload = (await request.json()) as ApprovalProxyRequest;
  const response = await fetch(
    `${baseUrl}/conversations/${encodeURIComponent(id)}/approve-send`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        approved: payload.approved ?? true,
        supervisor_id: payload.supervisor_id ?? "demo-supervisor",
        edited_reply: payload.edited_reply ?? null,
      }),
      cache: "no-store",
    },
  );

  const text = await response.text();
  let data: unknown = { detail: text };
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      data = { detail: text };
    }
  }

  return jsonResponse(data, response.status);
}
