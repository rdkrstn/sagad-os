import { getCurrentSession } from "@/lib/auth/session";
import { jsonResponse } from "@/lib/agent-studio-proxy";
import { proxyAgentStudioJson } from "@/lib/knowledge-proxy";

export async function GET(): Promise<Response> {
  const session = await getCurrentSession();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

  return proxyAgentStudioJson(session, "/knowledge/sources");
}
