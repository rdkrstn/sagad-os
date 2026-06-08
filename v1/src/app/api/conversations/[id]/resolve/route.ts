import { NextResponse } from "next/server";
import { getCurrentSession } from "@/lib/auth/session";
import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  hasApprovalRole,
  jsonResponse,
  parseAgentStudioResponse,
} from "@/lib/agent-studio-proxy";

export async function POST(
  _request: Request,
  context: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const session = await getCurrentSession();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }
  if (!hasApprovalRole(session.user.role)) {
    return jsonResponse({ detail: "Supervisor, admin, or owner role required." }, 403);
  }

  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return jsonResponse(
      { detail: "SAGAD_API_BASE_URL is not configured." },
      503,
    );
  }

  const { id } = await context.params;
  const response = await fetch(
    `${baseUrl}/conversations/${encodeURIComponent(id)}/resolve`,
    {
      method: "POST",
      headers: agentStudioHeaders(session),
      cache: "no-store",
    },
  );

  const data = await parseAgentStudioResponse(response);
  return jsonResponse(data, response.status);
}
