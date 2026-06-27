import { getCurrentSession } from "@/lib/auth/session";
import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  hasIntegrationAdminRole,
  jsonResponse,
  parseAgentStudioResponse,
} from "@/lib/agent-studio-proxy";

export async function POST(): Promise<Response> {
  const session = await getCurrentSession();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }
  if (!hasIntegrationAdminRole(session.user.role)) {
    return jsonResponse({ detail: "Owner or admin role required." }, 403);
  }

  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return jsonResponse(
      {
        chat: { ok: false, detail: "SAGAD_API_BASE_URL is not configured.", model: "" },
        embedding: { ok: false, detail: "SAGAD_API_BASE_URL is not configured.", model: "" },
      },
      200,
    );
  }

  const response = await fetch(`${baseUrl}/model-providers/test`, {
    method: "POST",
    headers: agentStudioHeaders(session),
    cache: "no-store",
  });

  return jsonResponse(await parseAgentStudioResponse(response), response.status);
}
