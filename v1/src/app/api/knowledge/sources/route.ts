import { auth } from "../../../../../auth";
import { jsonResponse } from "@/lib/agent-studio-proxy";
import { proxyAgentStudioJson } from "@/lib/knowledge-proxy";

export async function GET(): Promise<Response> {
  const session = await auth();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

  return proxyAgentStudioJson(session, "/knowledge/sources");
}
