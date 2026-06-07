import { getCurrentSession } from "@/lib/auth/session";
import { jsonResponse } from "@/lib/agent-studio-proxy";
import { proxyAgentStudioJson, type RouteContextWithId } from "@/lib/knowledge-proxy";

export async function POST(
  _request: Request,
  context: RouteContextWithId,
): Promise<Response> {
  const session = await getCurrentSession();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

  const { id } = await context.params;
  return proxyAgentStudioJson(
    session,
    `/knowledge/documents/${encodeURIComponent(id)}/approve`,
    { method: "POST" },
  );
}
