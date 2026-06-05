import { auth } from "../../../../../../auth";
import { jsonResponse } from "@/lib/agent-studio-proxy";
import { proxyAgentStudioJson, type RouteContextWithId } from "@/lib/knowledge-proxy";

export async function GET(
  _request: Request,
  context: RouteContextWithId,
): Promise<Response> {
  const session = await auth();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

  const { id } = await context.params;
  return proxyAgentStudioJson(
    session,
    `/knowledge/documents/${encodeURIComponent(id)}`,
  );
}
