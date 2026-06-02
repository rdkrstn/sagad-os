import { NextRequest, NextResponse } from "next/server";
import type { Session } from "next-auth";
import { auth } from "../../../../../../auth";

interface ApprovalProxyRequest {
  approved?: boolean;
  edited_reply?: string | null;
}

function agentStudioBaseUrl(): string | null {
  const value = process.env.SAGAD_API_BASE_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

function jsonResponse(payload: unknown, status: number): NextResponse {
  return NextResponse.json(payload, { status });
}

function agentStudioHeaders(session: Session): HeadersInit {
  const headers = new Headers();
  headers.set("Content-Type", "application/json");

  const secret = process.env.AGENT_STUDIO_INTERNAL_SECRET?.trim();
  if (secret) {
    headers.set("X-Sagad-Internal-Secret", secret);
  }
  if (session.user.id) {
    headers.set("X-Sagad-User-Id", session.user.id);
  }
  if (session.user.organizationId) {
    headers.set("X-Sagad-Org-Id", session.user.organizationId);
  }
  if (session.user.role) {
    headers.set("X-Sagad-Role", session.user.role);
  }

  return headers;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const session = await auth();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

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
      headers: agentStudioHeaders(session),
      body: JSON.stringify({
        approved: payload.approved ?? true,
        supervisor_id: session.user.id,
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
