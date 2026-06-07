import { getCurrentSession } from "@/lib/auth/session";
import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  jsonResponse,
  parseAgentStudioResponse,
} from "@/lib/agent-studio-proxy";

export async function GET(): Promise<Response> {
  const session = await getCurrentSession();
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

  const response = await fetch(`${baseUrl}/integration-configs`, {
    headers: agentStudioHeaders(session),
    cache: "no-store",
  });

  return jsonResponse(await parseAgentStudioResponse(response), response.status);
}
