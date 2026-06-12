import { getCurrentSession } from "@/lib/auth/session";
import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  jsonResponse,
  parseAgentStudioResponse,
} from "@/lib/agent-studio-proxy";

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function DELETE(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  const session = await getCurrentSession();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

  const { id } = await context.params;
  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return jsonResponse({ detail: "SAGAD_API_BASE_URL is not configured." }, 503);
  }

  const response = await fetch(`${baseUrl}/agents/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: agentStudioHeaders(session),
    cache: "no-store",
  });

  return jsonResponse(await parseAgentStudioResponse(response), response.status);
}
