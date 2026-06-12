import { getCurrentSession } from "@/lib/auth/session";
import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  jsonResponse,
} from "@/lib/agent-studio-proxy";

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(
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

  let upstream: Response;
  try {
    upstream = await fetch(
      `${baseUrl}/conversations/${encodeURIComponent(id)}/draft/stream`,
      {
        headers: agentStudioHeaders(session),
        cache: "no-store",
      },
    );
  } catch {
    return jsonResponse({ detail: "Agent Studio is unavailable." }, 502);
  }

  if (!upstream.ok || !upstream.body) {
    return jsonResponse(
      { detail: `Agent Studio returned HTTP ${upstream.status}.` },
      upstream.status,
    );
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
