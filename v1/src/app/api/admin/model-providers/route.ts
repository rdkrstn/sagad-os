import { NextRequest } from "next/server";
import { getCurrentSession } from "@/lib/auth/session";
import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  hasIntegrationAdminRole,
  jsonResponse,
  parseAgentStudioResponse,
} from "@/lib/agent-studio-proxy";

export async function PUT(request: NextRequest): Promise<Response> {
  const session = await getCurrentSession();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }
  if (!hasIntegrationAdminRole(session.user.role)) {
    return jsonResponse({ detail: "Owner or admin role required." }, 403);
  }

  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return jsonResponse({ detail: "SAGAD_API_BASE_URL is not configured." }, 503);
  }

  const response = await fetch(`${baseUrl}/model-providers`, {
    method: "PUT",
    headers: agentStudioHeaders(session),
    body: JSON.stringify(await request.json()),
    cache: "no-store",
  });

  return jsonResponse(await parseAgentStudioResponse(response), response.status);
}
