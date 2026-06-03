import { NextRequest } from "next/server";
import { auth } from "../../../../../auth";
import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  isIntegrationProvider,
  jsonResponse,
  parseAgentStudioResponse,
} from "@/lib/agent-studio-proxy";

interface RouteContext {
  params: Promise<{ provider: string }>;
}

async function providerFromContext(context: RouteContext): Promise<string | null> {
  const { provider } = await context.params;
  return isIntegrationProvider(provider) ? provider : null;
}

export async function PUT(
  request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  const session = await auth();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

  const provider = await providerFromContext(context);
  if (!provider) {
    return jsonResponse({ detail: "Unsupported integration provider." }, 404);
  }

  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return jsonResponse(
      { detail: "SAGAD_API_BASE_URL is not configured." },
      503,
    );
  }

  const response = await fetch(`${baseUrl}/integration-configs/${provider}`, {
    method: "PUT",
    headers: agentStudioHeaders(session),
    body: JSON.stringify(await request.json()),
    cache: "no-store",
  });

  return jsonResponse(await parseAgentStudioResponse(response), response.status);
}

export async function DELETE(
  _request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  const session = await auth();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

  const provider = await providerFromContext(context);
  if (!provider) {
    return jsonResponse({ detail: "Unsupported integration provider." }, 404);
  }

  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return jsonResponse(
      { detail: "SAGAD_API_BASE_URL is not configured." },
      503,
    );
  }

  const response = await fetch(
    `${baseUrl}/integration-configs/${provider}/disable`,
    {
      method: "POST",
      headers: agentStudioHeaders(session),
      cache: "no-store",
    },
  );

  return jsonResponse(await parseAgentStudioResponse(response), response.status);
}
