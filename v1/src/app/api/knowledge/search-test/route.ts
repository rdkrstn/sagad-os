import { auth } from "../../../../../auth";
import { jsonResponse } from "@/lib/agent-studio-proxy";
import { proxyAgentStudioJson } from "@/lib/knowledge-proxy";

interface KnowledgeSearchPayload {
  query?: string;
  intent?: string;
  risk_level?: "low" | "medium" | "high";
  limit?: number;
}

function safeLimit(value: number | undefined): number {
  if (!Number.isFinite(value)) {
    return 4;
  }

  return Math.min(10, Math.max(1, Math.trunc(value ?? 4)));
}

function normalizePayload(value: unknown): KnowledgeSearchPayload {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  const record = value as Record<string, unknown>;
  return {
    query: typeof record.query === "string" ? record.query : undefined,
    intent: typeof record.intent === "string" ? record.intent : undefined,
    risk_level:
      record.risk_level === "low" ||
      record.risk_level === "medium" ||
      record.risk_level === "high"
        ? record.risk_level
        : undefined,
    limit: typeof record.limit === "number" ? record.limit : undefined,
  };
}

export async function POST(request: Request): Promise<Response> {
  const session = await auth();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }

  const payload = normalizePayload(await request.json().catch(() => ({})));
  if (!payload.query?.trim()) {
    return jsonResponse({ detail: "Search query is required." }, 400);
  }

  return proxyAgentStudioJson(session, "/knowledge/search-test", {
    method: "POST",
    body: JSON.stringify({
      query: payload.query.trim(),
      intent: payload.intent ?? "general_support",
      risk_level: payload.risk_level ?? "medium",
      limit: safeLimit(payload.limit),
    }),
  });
}
