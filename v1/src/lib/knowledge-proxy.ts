import type { Session } from "next-auth";

import {
  agentStudioBaseUrl,
  agentStudioHeaders,
  jsonResponse,
  parseAgentStudioResponse,
} from "@/lib/agent-studio-proxy";

export interface RouteContextWithId {
  params: Promise<{ id: string }>;
}

export const KNOWLEDGE_UPLOAD_LIMITS = {
  maxFiles: 10,
  maxBytesPerFile: 10 * 1024 * 1024,
  allowedExtensions: new Set([
    ".md",
    ".markdown",
    ".txt",
    ".json",
    ".vtt",
    ".srt",
    ".pdf",
    ".docx",
    ".xlsx",
    ".csv",
  ]),
};

export function extensionOf(filename: string): string {
  const normalized = filename.toLowerCase();
  const dotIndex = normalized.lastIndexOf(".");
  return dotIndex >= 0 ? normalized.slice(dotIndex) : "";
}

export async function proxyAgentStudioJson(
  session: Session,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return jsonResponse({ detail: "SAGAD_API_BASE_URL is not configured." }, 503);
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers: {
        ...Object.fromEntries(new Headers(agentStudioHeaders(session))),
        ...(init.headers ? Object.fromEntries(new Headers(init.headers)) : {}),
      },
      cache: "no-store",
    });
  } catch {
    return jsonResponse({ detail: "Agent Studio is unavailable." }, 502);
  }

  return jsonResponse(await parseAgentStudioResponse(response), response.status);
}
