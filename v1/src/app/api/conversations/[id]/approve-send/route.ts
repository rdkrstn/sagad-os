import { NextRequest, NextResponse } from "next/server";
import { auth } from "../../../../../../auth";
import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  jsonResponse,
  parseAgentStudioResponse,
} from "@/lib/agent-studio-proxy";

interface ApprovalProxyRequest {
  approved?: boolean;
  edited_reply?: string | null;
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

  const data = await parseAgentStudioResponse(response);
  return jsonResponse(data, response.status);
}
