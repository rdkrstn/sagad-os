import { getCurrentSession } from "@/lib/auth/session";
import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  hasIntegrationAdminRole,
  isIntegrationProvider,
  jsonResponse,
  parseAgentStudioResponse,
} from "@/lib/agent-studio-proxy";

interface RouteContext {
  params: Promise<{ provider: string }>;
}

export async function POST(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  const session = await getCurrentSession();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }
  if (!hasIntegrationAdminRole(session.user.role)) {
    return jsonResponse({ detail: "Owner or admin role required." }, 403);
  }

  const { provider } = await context.params;
  if (!isIntegrationProvider(provider)) {
    return jsonResponse({ detail: "Unsupported integration provider." }, 404);
  }

  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return jsonResponse(
      { detail: "SAGAD_API_BASE_URL is not configured." },
      503,
    );
  }

  const response = await fetch(`${baseUrl}/integration-configs/${provider}/test`, {
    method: "POST",
    headers: agentStudioHeaders(session),
    cache: "no-store",
  });

  return jsonResponse(await parseAgentStudioResponse(response), response.status);
}
