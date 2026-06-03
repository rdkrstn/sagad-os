import { NextResponse } from "next/server";
import type { Session } from "next-auth";

export type IntegrationProvider = "chatwoot" | "twenty";

export function agentStudioBaseUrl(): string | null {
  const value = process.env.SAGAD_API_BASE_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

export function jsonResponse(payload: unknown, status: number): NextResponse {
  return NextResponse.json(payload, { status });
}

export function agentStudioHeaders(session: Session): HeadersInit {
  const headers = new Headers();
  headers.set("Content-Type", "application/json");

  const secret = process.env.AGENT_STUDIO_INTERNAL_SECRET?.trim();
  if (secret) {
    headers.set("X-Sagad-Internal-Secret", secret);
  }
  if (session.user.id) {
    headers.set("X-Sagad-User-Id", session.user.id);
  }
  if (session.user.organizationId) {
    headers.set("X-Sagad-Org-Id", session.user.organizationId);
  }
  if (session.user.role) {
    headers.set("X-Sagad-Role", session.user.role);
  }

  return headers;
}

export async function parseAgentStudioResponse(
  response: Response,
): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { detail: text };
  }
}

export function isIntegrationProvider(value: string): value is IntegrationProvider {
  return value === "chatwoot" || value === "twenty";
}
