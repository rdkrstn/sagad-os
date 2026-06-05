import { NextRequest } from "next/server";
import { auth } from "../../../../../auth";
import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  jsonResponse,
  parseAgentStudioResponse,
} from "@/lib/agent-studio-proxy";

export async function GET(request: NextRequest): Promise<Response> {
  const session = await auth();
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

  const upstreamUrl = new URL(`${baseUrl}/diagnostics/events`);
  const conversationId = request.nextUrl.searchParams.get("conversation_id");
  const limit = request.nextUrl.searchParams.get("limit");
  if (conversationId) {
    upstreamUrl.searchParams.set("conversation_id", conversationId);
  }
  if (limit) {
    upstreamUrl.searchParams.set("limit", limit);
  }

  const response = await fetch(upstreamUrl, {
    headers: agentStudioHeaders(session),
    cache: "no-store",
  });

  return jsonResponse(await parseAgentStudioResponse(response), response.status);
}
