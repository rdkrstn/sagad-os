import type {
  ClassifierIntent,
  ContactDriver,
  Conversation,
  ConversationChannel,
  CrmContact,
  DashboardData,
  McpTool,
  SopReference,
} from "@/lib/domain";
import {
  homeServicesDashboardData,
  mockAgents,
  mockContactDrivers,
  mockContacts,
  mockConversations,
  mockMcpTools,
  mockSopReferences,
  mockSupervisorPods,
} from "@/lib/mocks";
import { getCurrentSession } from "@/lib/auth/session";

type ViewRecord = Record<string, unknown>;
type ConversationView = Omit<Conversation, "messages" | "priority" | "status"> &
  ViewRecord;
type AgentView = ViewRecord;
type DriverView = ContactDriver & ViewRecord;
type SopView = SopReference & ViewRecord;
type ToolView = McpTool & ViewRecord;
type DashboardViewData = Omit<
  DashboardData,
  | "agents"
  | "contactDrivers"
  | "conversations"
  | "mcpTools"
  | "sopReferences"
  | "supervisorPods"
> &
  ViewRecord;

interface AgentStudioKnowledgeHit {
  id: string;
  title: string;
  category: string;
  source_path: string;
  score: number;
  excerpt: string;
}

interface AgentStudioMemoryHit {
  id: string;
  memory_type: string;
  content: string;
  source: string;
  score: number;
  conversation_id: string | null;
  chatwoot_conversation_id: string | null;
  source_message_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

interface AgentStudioQaFinding {
  label: string;
  status: "pass" | "watch" | "fail";
  detail: string;
}

interface AgentStudioToolPlan {
  id: string;
  provider: string;
  tool_name: string;
  action: string;
  risk_level: "low" | "medium" | "high";
  requires_approval: boolean;
  approved: boolean;
  dry_run: boolean;
  args: Record<string, unknown>;
}

interface AgentStudioToolResult {
  id: string;
  plan_id: string;
  provider: string;
  tool_name: string;
  status: "planned" | "dry_run" | "blocked" | "succeeded" | "failed";
  detail: string;
  external_id: string | null;
  data: Record<string, unknown>;
}

interface AgentStudioConversationMessage {
  id: string;
  sender_type: "customer" | "ai_agent" | "human_agent" | "system" | "tool";
  body: string;
  external_message_id: string | null;
  provider: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

interface AgentStudioChatwootInboxContext {
  id: string | null;
  name: string | null;
  channel_type: string | null;
  provider: string | null;
}

interface AgentStudioChatwootContext {
  normalized_channel: string | null;
  contact_last_seen_at: string | null;
  agent_last_seen_at: string | null;
  assignee_last_seen_at: string | null;
  last_activity_at: string | null;
  unread_count: number | null;
  can_reply: boolean | null;
  source_id: string | null;
  inbox: AgentStudioChatwootInboxContext | null;
  status: string | null;
  priority: string | null;
  labels: string[];
  waiting_since: string | null;
  fetch_status: "not_fetched" | "ready" | "failed" | "unconfigured";
  fetch_error: string | null;
  fetched_at: string | null;
}

interface AgentStudioConversation {
  id: string;
  chatwoot_conversation_id: string | null;
  chatwoot_message_id: string | null;
  customer_name: string;
  channel: string;
  incoming_message: string;
  normalized_message: string;
  intent: string;
  risk_level: "low" | "medium" | "high";
  memory_context?: AgentStudioMemoryHit[];
  memory_diagnostic?: Record<string, unknown>;
  retrieved_knowledge: AgentStudioKnowledgeHit[];
  tool_plans: AgentStudioToolPlan[];
  tool_results: AgentStudioToolResult[];
  chatwoot_context?: AgentStudioChatwootContext | null;
  draft_reply: string;
  qa_findings: AgentStudioQaFinding[];
  compliance_status: "pass" | "needs_review" | "blocked";
  approval_status: string;
  send_status: string;
  trace_url: string | null;
  messages?: AgentStudioConversationMessage[];
  created_at: string;
  updated_at: string;
}

interface AgentStudioConversationList {
  conversations: AgentStudioConversation[];
}

interface AgentStudioKnowledgeDocument {
  id: string;
  source_id: string | null;
  job_id: string | null;
  pack_slug: string;
  category: string;
  source_path: string;
  title: string;
  content: string;
  content_hash: string;
  version: number;
  approval_status: "needs_review" | "approved" | "archived";
  chunk_count: number;
  last_embedded_at?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface AgentStudioKnowledgeSource {
  id: string;
  source_type: string;
  name: string;
  status: string;
  sync_policy: string;
  last_synced_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface AgentStudioKnowledgeIngestionError {
  id: string;
  job_id: string;
  source_path: string;
  error_code: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

interface AgentStudioKnowledgeIngestionJob {
  id: string;
  source_id: string;
  source_name: string;
  source_type: string;
  status: string;
  total_files: number;
  processed_files: number;
  failed_files: number;
  summary: string;
  metadata: Record<string, unknown>;
  errors: AgentStudioKnowledgeIngestionError[];
  created_at: string;
  updated_at: string;
}

export interface IntegrationConnectionView {
  provider: "chatwoot" | "twenty";
  name: string;
  kind: string;
  status: string;
  configured: boolean;
  enabled: boolean;
  external: boolean;
  base_url: string | null;
  account_id: string | null;
  inbox_id: string | null;
  api_mode: string | null;
  dry_run: boolean;
  writes_enabled: boolean;
  has_api_access_token: boolean;
  has_webhook_token: boolean;
  has_api_key: boolean;
  missing: string[];
  detail: string;
  updated_at: string | null;
}

interface IntegrationConnectionList {
  connections: IntegrationConnectionView[];
}

type AgentStudioCatalogRecord = ViewRecord;

const demoNow = "2026-06-04T09:00:00+08:00";
const clone = <T>(value: T): T => structuredClone(value);
const agentStudioFetchTimeoutMs = 3000;

function viewRecord(value: unknown): ViewRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as ViewRecord)
    : {};
}

function viewText(
  row: ViewRecord,
  keys: string[],
  fallback = "",
): string {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number") return String(value);
    if (typeof value === "boolean") return value ? "Yes" : "No";
  }

  return fallback;
}

function viewRecordArray(row: ViewRecord, keys: string[]): ViewRecord[] {
  for (const key of keys) {
    const value = row[key];
    if (Array.isArray(value)) {
      return value.filter(
        (item): item is ViewRecord =>
          Boolean(item) && typeof item === "object" && !Array.isArray(item),
      );
    }
  }

  return [];
}

function viewPayloadArray(
  payload: unknown,
  keys: string[],
): ViewRecord[] | null {
  if (Array.isArray(payload)) {
    return payload.filter(
      (item): item is ViewRecord =>
        Boolean(item) && typeof item === "object" && !Array.isArray(item),
    );
  }

  const row = viewRecord(payload);
  for (const key of keys) {
    const value = row[key];
    if (Array.isArray(value)) {
      return value.filter(
        (item): item is ViewRecord =>
          Boolean(item) && typeof item === "object" && !Array.isArray(item),
      );
    }
  }

  return null;
}

function viewStringArray(row: ViewRecord, keys: string[]): string[] {
  for (const key of keys) {
    const value = row[key];
    if (Array.isArray(value)) {
      return value
        .map((item) => String(item).trim())
        .filter((item) => item.length > 0);
    }
    if (typeof value === "string" && value.trim()) {
      return value
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
    }
  }

  return [];
}

function viewBoolean(
  row: ViewRecord,
  keys: string[],
  fallback = false,
): boolean {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "boolean") return value;
    if (typeof value === "string") {
      const normalized = value.trim().toLowerCase();
      if (["true", "yes", "1", "enabled", "required"].includes(normalized)) {
        return true;
      }
      if (["false", "no", "0", "disabled", "none"].includes(normalized)) {
        return false;
      }
    }
  }

  return fallback;
}

function viewOptionalBoolean(
  row: ViewRecord,
  keys: string[],
): boolean | null {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "boolean") return value;
    if (typeof value === "string") {
      const normalized = value.trim().toLowerCase();
      if (["true", "yes", "1", "enabled", "required"].includes(normalized)) {
        return true;
      }
      if (["false", "no", "0", "disabled", "none"].includes(normalized)) {
        return false;
      }
    }
  }

  return null;
}

function viewNestedRecord(row: ViewRecord, keys: string[]): ViewRecord {
  for (const key of keys) {
    const value = viewRecord(row[key]);
    if (Object.keys(value).length > 0) return value;
  }

  return {};
}

function uniqueStrings(values: string[]): string[] {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function jsonPreview(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

const contactById = new Map(mockContacts.map((contact) => [contact.id, contact]));
const agentById = new Map(mockAgents.map((agent) => [agent.id, agent]));
const podById = new Map(mockSupervisorPods.map((pod) => [pod.id, pod]));
const toolById = new Map(mockMcpTools.map((tool) => [tool.id, tool]));

function agentStudioBaseUrl(): string | null {
  const value = process.env.SAGAD_API_BASE_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

type AgentStudioConnectionStatus =
  | "connected"
  | "not_configured"
  | "unauthorized"
  | "unreachable";

type AgentStudioFetchResult<T> = {
  data: T | null;
  detail?: string;
  status: AgentStudioConnectionStatus;
  statusCode?: number;
};

function connectionStatusFromHttp(statusCode: number): AgentStudioConnectionStatus {
  return statusCode === 401 || statusCode === 403 ? "unauthorized" : "unreachable";
}

async function fetchAgentStudioJson<T>(
  path: string,
  readData: (payload: unknown) => T | null,
): Promise<AgentStudioFetchResult<T>> {
  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return {
      data: null,
      detail: "SAGAD_API_BASE_URL is not configured.",
      status: "not_configured",
    };
  }

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      headers: await agentStudioHeaders(),
      cache: "no-store",
      signal: AbortSignal.timeout(agentStudioFetchTimeoutMs),
    });

    if (!response.ok) {
      return {
        data: null,
        detail: `Agent Studio returned HTTP ${response.status}.`,
        status: connectionStatusFromHttp(response.status),
        statusCode: response.status,
      };
    }

    const payload = (await response.json()) as unknown;
    const data = readData(payload);
    if (data === null) {
      return {
        data: null,
        detail: "Agent Studio returned an unexpected response shape.",
        status: "unreachable",
        statusCode: response.status,
      };
    }

    return {
      data,
      status: "connected",
      statusCode: response.status,
    };
  } catch {
    return {
      data: null,
      detail: `Agent Studio is not reachable at ${baseUrl}.`,
      status: "unreachable",
    };
  }
}

async function agentStudioHeaders(): Promise<HeadersInit> {
  const headers = new Headers();
  const secret = process.env.AGENT_STUDIO_INTERNAL_SECRET?.trim();
  if (secret) {
    headers.set("X-Sagad-Internal-Secret", secret);
  }

  const session = await getCurrentSession().catch(() => null);
  if (session?.user?.id) {
    headers.set("X-Sagad-User-Id", session.user.id);
  }
  if (session?.user?.organizationId) {
    headers.set("X-Sagad-Org-Id", session.user.organizationId);
  }
  if (session?.user?.role) {
    headers.set("X-Sagad-Role", session.user.role);
  }

  return headers;
}

async function fetchAgentStudioConversations(): Promise<AgentStudioConversation[] | null> {
  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return null;
  }

  try {
    const response = await fetch(`${baseUrl}/conversations`, {
      headers: await agentStudioHeaders(),
      cache: "no-store",
      signal: AbortSignal.timeout(agentStudioFetchTimeoutMs),
    });

    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as AgentStudioConversationList;
    return Array.isArray(payload.conversations) ? payload.conversations : null;
  } catch {
    return null;
  }
}

async function fetchAgentStudioIntegrationConnections(): Promise<IntegrationConnectionView[] | null> {
  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return null;
  }

  try {
    const response = await fetch(`${baseUrl}/integration-configs`, {
      headers: await agentStudioHeaders(),
      cache: "no-store",
      signal: AbortSignal.timeout(agentStudioFetchTimeoutMs),
    });

    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as IntegrationConnectionList;
    return Array.isArray(payload.connections) ? payload.connections : null;
  } catch {
    return null;
  }
}

async function fetchAgentStudioKnowledgeDocuments(): Promise<
  AgentStudioFetchResult<AgentStudioKnowledgeDocument[]>
> {
  return fetchAgentStudioJson("/knowledge/documents", (payload) => {
    const documents = viewRecord(payload).documents;
    return Array.isArray(documents) ? documents : null;
  });
}

async function fetchAgentStudioKnowledgeJobs(): Promise<
  AgentStudioFetchResult<AgentStudioKnowledgeIngestionJob[]>
> {
  return fetchAgentStudioJson("/knowledge/ingestion-jobs", (payload) => {
    const jobs = viewRecord(payload).jobs;
    return Array.isArray(jobs) ? jobs : null;
  });
}

async function fetchAgentStudioKnowledgeSources(): Promise<
  AgentStudioFetchResult<AgentStudioKnowledgeSource[]>
> {
  return fetchAgentStudioJson("/knowledge/sources", (payload) => {
    const sources = viewRecord(payload).sources;
    return Array.isArray(sources) ? sources : null;
  });
}

async function fetchAgentStudioLiteLlmHealth(): Promise<AgentStudioFetchResult<ViewRecord>> {
  return fetchAgentStudioJson("/integrations/litellm/health", (payload) => {
    const record = viewRecord(payload);
    return Object.keys(record).length > 0 ? record : null;
  });
}

async function fetchAgentStudioToolManifests(): Promise<
  AgentStudioFetchResult<AgentStudioCatalogRecord[]>
> {
  return fetchAgentStudioJson("/tools/manifests", (payload) =>
    viewPayloadArray(payload, [
      "manifests",
      "tool_manifests",
      "toolManifests",
      "tools",
      "items",
    ]),
  );
}

async function fetchAgentStudioSkills(): Promise<
  AgentStudioFetchResult<AgentStudioCatalogRecord[]>
> {
  return fetchAgentStudioJson("/skills", (payload) =>
    viewPayloadArray(payload, [
      "skills",
      "skill_definitions",
      "skillDefinitions",
      "available_skills",
      "availableSkills",
      "items",
    ]),
  );
}

async function fetchAgentStudioMcpDescriptors(): Promise<
  AgentStudioFetchResult<AgentStudioCatalogRecord[]>
> {
  return fetchAgentStudioJson("/mcp/descriptors", (payload) =>
    viewPayloadArray(payload, [
      "descriptors",
      "mcp_descriptors",
      "mcpDescriptors",
      "tools",
      "items",
    ]),
  );
}

function summarizeAgentStudioStatus(
  results: Array<AgentStudioFetchResult<unknown>>,
): AgentStudioConnectionStatus {
  if (results.some((result) => result.status === "connected")) {
    return "connected";
  }

  if (results.some((result) => result.status === "unauthorized")) {
    return "unauthorized";
  }

  if (results.every((result) => result.status === "not_configured")) {
    return "not_configured";
  }

  return "unreachable";
}

function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function normalizeConversationChannel(value: string | null | undefined): ConversationChannel {
  const normalized = (value ?? "").trim().toLowerCase();
  if (
    [
      "web_chat",
      "sms",
      "email",
      "voice",
      "facebook",
      "instagram",
      "whatsapp",
      "telegram",
      "line",
      "api",
      "unknown",
    ].includes(normalized)
  ) {
    return normalized as ConversationChannel;
  }
  return "unknown";
}

function conversationChannelLabel(channel: ConversationChannel): string {
  const labels: Record<ConversationChannel, string> = {
    web_chat: "Web Chat",
    sms: "SMS",
    email: "Email",
    voice: "Voice",
    facebook: "Facebook",
    instagram: "Instagram",
    whatsapp: "WhatsApp",
    telegram: "Telegram",
    line: "LINE",
    api: "API",
    unknown: "Unknown",
  };
  return labels[channel];
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function minutesBetween(startIso: string, endIso = demoNow): number {
  const diff = Date.parse(endIso) - Date.parse(startIso);
  return Math.max(1, Math.round(diff / 60_000));
}

function minutesLabel(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder > 0 ? `${hours}h ${remainder}m` : `${hours}h`;
}

function moneyLabel(contact: CrmContact): string {
  const amount = contact.serviceHistory.reduce(
    (sum, item) => sum + item.invoiceTotal.amount,
    0,
  );

  return amount > 0 ? `$${amount.toLocaleString("en-US")}` : "New lead";
}

function lastCustomerMessage(conversation: Conversation): string {
  return (
    [...conversation.messages]
      .reverse()
      .find((message) => message.senderType === "customer")?.body ??
    conversation.subject
  );
}

function lastAgentDraft(conversation: Conversation): string {
  const reviewedMessage =
    conversation.reviewDecision?.finalMessage ??
    conversation.reviewDecision?.proposedMessage;

  if (reviewedMessage) {
    return reviewedMessage;
  }

  const aiOrHumanMessage = [...conversation.messages]
    .reverse()
    .find(
      (message) =>
        message.senderType === "ai_agent" || message.senderType === "human_agent",
    );

  if (aiOrHumanMessage) {
    return aiOrHumanMessage.body;
  }

  if (conversation.classifier.intent === "crm_tool_failure") {
    return "I am having trouble saving that appointment. I will keep the slot on hold and have a team member confirm it manually.";
  }

  return "Thanks. Let me check the right next step and get back to you shortly.";
}

function routeForIntent(intent: string): string {
  if (intent.includes("pricing")) return "Sales";
  if (intent.includes("support")) return "Support";
  if (intent.includes("tool")) return "Support";
  if (intent.includes("refund") || intent.includes("cancellation")) return "Support";
  if (intent.includes("unknown")) return "Support";
  return "Supervisor";
}

function laneForConversation(conversation: Conversation): string {
  const hasFailedMessage = conversation.messages.some(
    (message) => message.deliveryStatus === "failed",
  );

  if (
    hasFailedMessage ||
    conversation.langGraphRun.interruptStatus === "failed" ||
    conversation.classifier.intent === "crm_tool_failure"
  ) {
    return "Failed tool/send";
  }

  if (
    conversation.status === "human_takeover" ||
    conversation.reviewDecision?.status === "escalated"
  ) {
    return "Escalated";
  }

  if (conversation.classifier.confidence < 0.8) {
    return "Low confidence";
  }

  if (
    conversation.status === "needs_review" ||
    conversation.langGraphRun.interruptStatus === "pending_approval"
  ) {
    return "Approval";
  }

  return "Monitoring";
}

function priorityLabel(priority: Conversation["priority"]): string {
  if (priority === "urgent") return "High risk";
  if (priority === "high") return "High";
  if (priority === "low") return "Low";
  return "Normal";
}

function contactContext(contact: CrmContact | undefined): ViewRecord {
  if (!contact) {
    return {
      provider: "Twenty CRM",
      providerStatus: "Twenty external",
      source: "Sagad OS adapter",
      mode: "Mock fallback",
      lifecycle: "Unknown",
      lastJob: "n/a",
      customerValue: "n/a",
      risk: "Unknown",
      owner: "Ops",
      area: "n/a",
    };
  }

  const lastService =
    contact.serviceHistory[0]?.serviceType ??
    contact.appointments[0]?.serviceType ??
    "No completed job";

  return {
    provider: "Twenty CRM",
    providerStatus: "Twenty external",
    source: "Sagad OS adapter",
    mode: "Mock fallback",
    lifecycle: titleCase(contact.leadStage),
    stage: titleCase(contact.leadStage),
    lastJob: lastService,
    lastService,
    customerValue: moneyLabel(contact),
    ltv: moneyLabel(contact),
    risk: contact.tags.includes("human-takeover")
      ? "High"
      : contact.tags.includes("verification-required")
        ? "Medium"
        : "Normal",
    accountRisk: contact.tags.includes("refund") ? "High" : "Normal",
    owner: contact.tasks[0]?.ownerId
      ? (agentById.get(contact.tasks[0].ownerId)?.name ?? "Ops")
      : "Ops",
    assignedRep: contact.tasks[0]?.ownerId
      ? (agentById.get(contact.tasks[0].ownerId)?.name ?? "Ops")
      : "Ops",
    area: contact.city,
    market: contact.city,
    tags: contact.tags,
    notes: contact.notes,
    tasks: contact.tasks.map((task) => task.title),
    serviceHistory: contact.serviceHistory.map((item) => item.serviceType),
  };
}

function decisionTrail(conversation: Conversation): ViewRecord[] {
  if (conversation.auditEvents?.length) {
    return conversation.auditEvents.map((event) => ({
      step: event.label,
      label: event.label,
      status: event.status,
      rationale: event.detail,
      detail: event.detail,
      actor: titleCase(event.actor),
      type: event.type,
      createdAt: event.createdAt,
    }));
  }

  const route = routeForIntent(conversation.classifier.intent);
  const trail: ViewRecord[] = [
    {
      step: "Debounce and normalize",
      status: "Complete",
      rationale: "Inbound message was grouped, normalized, and prepared for classification.",
    },
    {
      step: "Classifier",
      status: percent(conversation.classifier.confidence),
      rationale: conversation.classifier.summary,
    },
    {
      step: "Router",
      status: route,
      rationale: `${titleCase(conversation.classifier.intent)} routed to the ${route} lane.`,
    },
    {
      step: "LangGraph node",
      status: titleCase(conversation.langGraphRun.currentNode),
      rationale: `Thread ${conversation.langGraphRun.threadId}; interrupt status ${titleCase(
        conversation.langGraphRun.interruptStatus,
      )}.`,
    },
  ];

  if (conversation.reviewDecision) {
    trail.push({
      step: "Supervisor approval",
      status: titleCase(conversation.reviewDecision.status),
      rationale: conversation.reviewDecision.reason,
    });
  }

  for (const toolId of conversation.toolCallIds) {
    const tool = toolById.get(toolId);
    trail.push({
      step: tool?.label ?? toolId,
      status: titleCase(tool?.status ?? "queued"),
      rationale:
        tool?.description ??
        "Tool call was recorded by the orchestration layer for later review.",
    });
  }

  return trail;
}

function knowledgeForConversation(conversation: Conversation): ViewRecord[] {
  const matches = mockSopReferences.filter((reference) =>
    reference.appliesToIntents.includes(conversation.classifier.intent),
  );
  const references = matches.length > 0 ? matches : mockSopReferences.slice(0, 2);

  return references.map((reference, index) => ({
    title: reference.title,
    category: reference.section,
    source: reference.url,
    score: Number((1 - index * 0.08).toFixed(2)),
    excerpt: reference.summary,
  }));
}

function laneForAgentStudioConversation(conversation: AgentStudioConversation): string {
  if (conversation.send_status === "failed" || conversation.approval_status === "send_failed") {
    return "Failed tool/send";
  }
  if (conversation.risk_level === "high") {
    return "Escalated";
  }
  if (conversation.approval_status === "needs_approval") {
    return "Approval";
  }
  return "Monitoring";
}

function deliveryStatusForAgentStudioMessage(
  message: AgentStudioConversationMessage,
  conversation: AgentStudioConversation,
): string {
  const payload = message.payload ?? {};
  const rawStatus = String(
    payload.delivery_status ??
      payload.deliveryStatus ??
      payload.message_status ??
      payload.messageStatus ??
      payload.status ??
      "",
  ).toLowerCase();

  if (rawStatus.includes("seen") || rawStatus.includes("read")) return "seen";
  if (rawStatus.includes("delivered")) return "delivered";
  if (rawStatus.includes("sent")) return "sent";
  if (rawStatus.includes("fail") || rawStatus.includes("error")) return "failed";
  if (rawStatus.includes("queue") || rawStatus.includes("pending")) return "queued";

  if (message.sender_type === "customer") return "received";
  if (message.sender_type !== "ai_agent" && message.sender_type !== "human_agent") {
    return "logged";
  }

  if (conversation.send_status === "dry_run") return "dry_run";
  if (conversation.send_status === "sent") return "sent";
  if (conversation.send_status === "failed") return "failed";
  return "not_sent";
}

function classifierIntentForAgentStudio(intent: string): ClassifierIntent {
  if (intent === "pricing_lead") return "pricing_lead";
  if (intent === "general_support") return "general_support";
  if (intent === "refund_or_cancellation") return "refund_or_cancellation";
  if (intent === "booking_or_support") {
    return "account_support";
  }
  return "unknown";
}

function nonEmptyRecord(records: ViewRecord[]): ViewRecord {
  return records.find((record) => Object.keys(record).length > 0) ?? {};
}

function toolPolicyMetadata(
  plan: ViewRecord,
  result: ViewRecord = {},
): ViewRecord {
  const args = viewRecord(plan.args);
  const data = viewRecord(result.data);
  const decision = nonEmptyRecord([
    viewNestedRecord(plan, ["policy_decision", "policyDecision"]),
    viewNestedRecord(result, ["policy_decision", "policyDecision"]),
    viewNestedRecord(args, ["policy_decision", "policyDecision", "decision"]),
    viewNestedRecord(data, ["policy_decision", "policyDecision", "decision"]),
  ]);
  const allowed =
    viewOptionalBoolean(decision, ["allowed"]) ??
    viewOptionalBoolean(args, ["allowed"]) ??
    viewOptionalBoolean(data, ["allowed"]);
  const requiresApproval =
    viewOptionalBoolean(decision, ["requires_approval", "requiresApproval"]) ??
    viewOptionalBoolean(plan, ["requires_approval", "requiresApproval"]) ??
    viewOptionalBoolean(args, ["requires_approval", "requiresApproval"]) ??
    viewOptionalBoolean(data, ["requires_approval", "requiresApproval"]) ??
    false;
  const dryRun =
    viewOptionalBoolean(decision, ["dry_run", "dryRun"]) ??
    viewOptionalBoolean(plan, ["dry_run", "dryRun"]) ??
    viewOptionalBoolean(result, ["dry_run", "dryRun"]) ??
    viewOptionalBoolean(args, ["dry_run", "dryRun"]) ??
    viewOptionalBoolean(data, ["dry_run", "dryRun"]) ??
    viewText(result, ["status"], "").toLowerCase().includes("dry");
  const blockedReason =
    viewText(decision, ["blocked_reason", "blockedReason"], "") ||
    viewText(args, ["blocked_reason", "blockedReason"], "") ||
    viewText(data, ["blocked_reason", "blockedReason"], "");
  const policyReasons = uniqueStrings([
    ...viewStringArray(decision, [
      "policy_reasons",
      "policyReasons",
      "reasons",
    ]),
    ...viewStringArray(args, ["policy_reasons", "policyReasons", "reasons"]),
    ...viewStringArray(data, ["policy_reasons", "policyReasons", "reasons"]),
    blockedReason,
  ]);

  return {
    allowed,
    status: allowed === null ? "Policy recorded" : allowed ? "Allowed" : "Blocked",
    requiresApproval,
    approval: requiresApproval ? "Required" : "Not required",
    dryRun,
    liveMode: dryRun ? "Dry-run" : "Live",
    blockedReason,
    policyReasons:
      policyReasons.length > 0
        ? policyReasons
        : [
            requiresApproval
              ? "Tool requires approval before live execution."
              : "Tool passed through Agent Studio policy.",
          ],
    decision,
  };
}

function toAgentStudioConversationView(
  conversation: AgentStudioConversation,
): ConversationView {
  const lane = laneForAgentStudioConversation(conversation);
  const confidence = conversation.retrieved_knowledge.length > 0 ? 0.88 : 0.68;
  const chatwootContext = conversation.chatwoot_context ?? null;
  const normalizedChannel = normalizeConversationChannel(
    chatwootContext?.normalized_channel ?? conversation.channel,
  );
  const channelLabel = conversationChannelLabel(normalizedChannel);
  const ageMinutes = minutesBetween(conversation.created_at, new Date().toISOString());
  const knowledgeContext = conversation.retrieved_knowledge.map((hit) => ({
    title: hit.title,
    category: titleCase(hit.category),
    source: hit.source_path,
    score: hit.score,
    excerpt: hit.excerpt,
  }));
  const memoryContext = (conversation.memory_context ?? []).map((hit) => ({
    id: hit.id,
    memoryType: titleCase(hit.memory_type),
    content: hit.content,
    source: titleCase(hit.source),
    score: hit.score,
    conversationId: hit.conversation_id,
    chatwootConversationId: hit.chatwoot_conversation_id,
    sourceMessageId: hit.source_message_id,
    metadata: hit.metadata,
    createdAt: hit.created_at,
  }));
  const qaCompliance = conversation.qa_findings.map((finding) => ({
    label: finding.label,
    status: titleCase(finding.status),
    detail: finding.detail,
  }));
  const rawToolPlans = conversation.tool_plans ?? [];
  const rawToolResults = conversation.tool_results ?? [];
  const rawResultByPlanId = new Map(
    rawToolResults.map((result) => [result.plan_id, result]),
  );
  const rawPlanById = new Map(rawToolPlans.map((plan) => [plan.id, plan]));
  const toolPlans = rawToolPlans.map((plan) => {
    const result = rawResultByPlanId.get(plan.id);
    const policyDecision = toolPolicyMetadata(
      {
        ...plan,
        args: plan.args,
      },
      result
        ? {
            ...result,
            data: result.data,
          }
        : {},
    );

    return {
      id: plan.id,
      provider: plan.provider,
      toolName: plan.tool_name,
      action: plan.action,
      riskLevel: titleCase(plan.risk_level),
      requiresApproval: plan.requires_approval,
      approved: plan.approved,
      dryRun: plan.dry_run,
      args: plan.args,
      policyDecision,
      policyReasons: viewStringArray(policyDecision, ["policyReasons"]),
      blockedReason: viewText(policyDecision, ["blockedReason"], ""),
      policyStatus: viewText(policyDecision, ["status"], "Policy recorded"),
      liveMode: viewText(policyDecision, ["liveMode"], plan.dry_run ? "Dry-run" : "Live"),
    };
  });
  const toolResults = rawToolResults.map((result) => {
    const plan = rawPlanById.get(result.plan_id);
    const policyDecision = toolPolicyMetadata(
      plan
        ? {
            ...plan,
            args: plan.args,
          }
        : {},
      {
        ...result,
        data: result.data,
      },
    );

    return {
      id: result.id,
      planId: result.plan_id,
      provider: result.provider,
      toolName: result.tool_name,
      status: titleCase(result.status),
      detail: result.detail,
      externalId: result.external_id,
      data: result.data,
      action: plan?.action ?? "",
      riskLevel: plan ? titleCase(plan.risk_level) : "Unknown",
      requiresApproval:
        plan?.requires_approval ??
        viewBoolean(policyDecision, ["requiresApproval"]),
      dryRun:
        plan?.dry_run ??
        viewBoolean(policyDecision, ["dryRun"], result.status === "dry_run"),
      policyDecision,
      policyReasons: viewStringArray(policyDecision, ["policyReasons"]),
      blockedReason: viewText(policyDecision, ["blockedReason"], ""),
      policyStatus: viewText(policyDecision, ["status"], "Policy recorded"),
      liveMode: viewText(policyDecision, ["liveMode"], result.status === "dry_run" ? "Dry-run" : "Live"),
      httpStatus:
        typeof result.data.http_status === "number"
          ? result.data.http_status
          : null,
      responseExcerpt:
        typeof result.data.response_excerpt === "string"
          ? result.data.response_excerpt
          : "",
      targetUrl:
        typeof result.data.target_url === "string" ? result.data.target_url : "",
      errorType:
        typeof result.data.error_type === "string" ? result.data.error_type : "",
    };
  });
  const resultViewByPlanId = new Map(
    toolResults.map((result) => [String(result.planId), result]),
  );
  const toolEvidence = [
    ...toolPlans.map((plan) => {
      const result = resultViewByPlanId.get(String(plan.id));
      return {
        id: `${plan.id}-${result?.id ?? "pending"}`,
        planId: plan.id,
        resultId: result?.id ?? "",
        provider: plan.provider,
        toolName: plan.toolName,
        action: plan.action,
        planStatus: plan.policyStatus,
        resultStatus: result?.status ?? "No result",
        detail: result?.detail ?? plan.action,
        externalId: result?.externalId ?? "",
        riskLevel: plan.riskLevel,
        requiresApproval: plan.requiresApproval,
        approved: plan.approved,
        dryRun: plan.dryRun,
        liveMode: plan.liveMode,
        args: plan.args,
        resultData: result?.data ?? {},
        httpStatus: result?.httpStatus ?? null,
        responseExcerpt: result?.responseExcerpt ?? "",
        targetUrl: result?.targetUrl ?? "",
        errorType: result?.errorType ?? "",
        policyDecision: plan.policyDecision,
        policyReasons: plan.policyReasons,
        blockedReason: plan.blockedReason,
      };
    }),
    ...toolResults
      .filter((result) => !rawPlanById.has(String(result.planId)))
      .map((result) => ({
        id: `${result.planId || "orphan"}-${result.id}`,
        planId: result.planId,
        resultId: result.id,
        provider: result.provider,
        toolName: result.toolName,
        action: result.action,
        planStatus: result.policyStatus,
        resultStatus: result.status,
        detail: result.detail,
        externalId: result.externalId ?? "",
        riskLevel: result.riskLevel,
        requiresApproval: result.requiresApproval,
        approved: false,
        dryRun: result.dryRun,
        liveMode: result.liveMode,
        args: {},
        resultData: result.data,
        httpStatus: result.httpStatus,
        responseExcerpt: result.responseExcerpt,
        targetUrl: result.targetUrl,
        errorType: result.errorType,
        policyDecision: result.policyDecision,
        policyReasons: result.policyReasons,
        blockedReason: result.blockedReason,
      })),
  ];
  const policyDecisions = toolEvidence.map((item) => ({
    id: `${item.planId || item.resultId}-policy`,
    toolName: item.toolName,
    status: viewText(viewRecord(item.policyDecision), ["status"], item.planStatus),
    riskLevel: item.riskLevel,
    requiresApproval: item.requiresApproval,
    dryRun: item.dryRun,
    liveMode: item.liveMode,
    blockedReason: item.blockedReason,
    policyReasons: item.policyReasons,
    detail:
      item.policyReasons.length > 0
        ? item.policyReasons.join(" ")
        : "Tool policy decision was recorded by Agent Studio.",
  }));
  const threadMessages =
    conversation.messages && conversation.messages.length > 0
      ? conversation.messages
      : [
          {
            id: `${conversation.id}-inbound`,
            sender_type: "customer" as const,
            body: conversation.incoming_message,
            external_message_id: conversation.chatwoot_message_id,
            provider: "chatwoot",
            payload: {},
            created_at: conversation.created_at,
          },
        ];
  const latestCustomerMessage =
    [...threadMessages]
      .reverse()
      .find((message) => message.sender_type === "customer")?.body ??
    conversation.incoming_message;

  return {
    id: conversation.id,
    contactId: `chatwoot-${conversation.chatwoot_conversation_id ?? conversation.id}`,
    assignedAgentId: "agent-ai-dispatch",
    supervisorPodId: "pod-intake",
    channel: normalizedChannel,
    sourceChannel: channelLabel,
    subject: latestCustomerMessage.slice(0, 80),
    openedAt: conversation.created_at,
    updatedAt: conversation.updated_at,
    slaDueAt: conversation.updated_at,
    classifier: {
      intent: classifierIntentForAgentStudio(conversation.intent),
      confidence,
      sentiment: conversation.risk_level === "high" ? "frustrated" : "neutral",
      language: "en",
      summary: `${titleCase(conversation.intent)} from Chatwoot; ${conversation.compliance_status}.`,
      urgencyScore: conversation.risk_level === "high" ? 92 : 56,
    },
    langGraphRun: {
      threadId: conversation.id,
      currentNode: "await_supervisor_approval",
      interruptStatus: "pending_approval",
      approvalPayload: {
        reviewDecisionId: conversation.id,
        proposedAction: "send_approved_chatwoot_reply",
        riskLevel: conversation.risk_level,
      },
      resumeAction: "approve",
      traceUrl: conversation.trace_url ?? "LangSmith not configured",
      lastUpdatedAt: conversation.updated_at,
    },
    toolCallIds: toolResults.map((result) => result.id),
    toolPlans,
    toolResults,
    toolEvidence,
    policyDecisions,
    deliveryResults: toolResults,
    customerName: conversation.customer_name,
    contact: conversation.customer_name,
    name: conversation.customer_name,
    source: "Chatwoot",
    channelProvider: "Chatwoot",
    provider: "Chatwoot",
    chatwootContext,
    chatwootFetchStatus: chatwootContext?.fetch_status ?? "not_fetched",
    chatwootFetchError: chatwootContext?.fetch_error ?? "",
    inboxName: chatwootContext?.inbox?.name ?? "Chatwoot inbox",
    inboxId: chatwootContext?.inbox?.id ?? "",
    inboxChannelType: chatwootContext?.inbox?.channel_type ?? "",
    sourceId: chatwootContext?.source_id ?? "",
    chatwootStatus: chatwootContext?.status ?? "",
    unreadCount: chatwootContext?.unread_count ?? 0,
    canReply:
      chatwootContext?.can_reply === null || chatwootContext?.can_reply === undefined
        ? "Unknown"
        : chatwootContext.can_reply
          ? "Yes"
          : "No",
    lastActivityAt: chatwootContext?.last_activity_at ?? conversation.updated_at,
    contactLastSeenAt: chatwootContext?.contact_last_seen_at ?? "",
    agentLastSeenAt: chatwootContext?.agent_last_seen_at ?? "",
    assigneeLastSeenAt: chatwootContext?.assignee_last_seen_at ?? "",
    lane,
    queueType: lane,
    reason: "Agent Studio generated a draft that requires supervisor approval before sending.",
    queueReason: "Supervisor-gated Chatwoot send policy",
    intent: titleCase(conversation.intent),
    driver: titleCase(conversation.intent),
    confidence: percent(confidence),
    aiConfidence: percent(confidence),
    age: minutesLabel(ageMinutes),
    waitTime: minutesLabel(minutesBetween(conversation.updated_at, new Date().toISOString())),
    oldestAge: minutesLabel(ageMinutes),
    priority: conversation.risk_level === "high" ? "High risk" : "Normal",
    severity: titleCase(conversation.risk_level),
    attempts: 1,
    toolAttempts: 1,
    status: titleCase(conversation.approval_status),
    queueStatus: lane,
    summary: `${titleCase(conversation.intent)} requires supervisor approval.`,
    lastMessage: latestCustomerMessage,
    draftReply: conversation.draft_reply,
    suggestedReply: conversation.draft_reply,
    assignedTo: "Sagad Dispatch AI",
    supervisorPod: "Intake Pod",
    hitlStatus: titleCase(conversation.approval_status),
    sendStatus: titleCase(conversation.send_status),
    complianceStatus: titleCase(conversation.compliance_status),
    knowledgeContext,
    memoryContext,
    memoryDiagnostic: conversation.memory_diagnostic ?? {},
    qaCompliance,
    qaFindings: qaCompliance,
    qa_findings: qaCompliance,
    policyChecks: policyDecisions,
    toolPolicyDecisions: policyDecisions,
    crmContext: {
      provider: "Twenty CRM",
      providerStatus: "Twenty external",
      source: "Agent Studio adapter",
      mode: "Disabled or dry-run until Agent Studio env is configured",
      lifecycle: "Chatwoot visitor",
      lastJob: "n/a",
      customerValue: "Unknown",
      risk: titleCase(conversation.risk_level),
      owner: "Intake Pod",
      area: channelLabel,
    },
    customerContext: {
      lifecycle: "Chatwoot visitor",
      lastJob: "n/a",
      customerValue: "Unknown",
      risk: titleCase(conversation.risk_level),
      owner: "Intake Pod",
      area: channelLabel,
    },
    decisionTrail: [
      {
        step: "Chatwoot webhook",
        status: "Received",
        rationale: "Agent Studio accepted the inbound Chatwoot message.",
      },
      {
        step: "Classifier",
        status: percent(confidence),
        rationale: `${titleCase(conversation.intent)} with ${titleCase(
          conversation.risk_level,
        )} risk.`,
      },
      {
        step: "Knowledge retrieval",
        status: `${conversation.retrieved_knowledge.length} hits`,
        rationale: "Retrieved Markdown KB/SOP/QA/compliance context.",
      },
      {
        step: "QA/Compliance gate",
        status: titleCase(conversation.compliance_status),
        rationale: "Supervisor-gated preview policy requires approval before send.",
      },
      ...toolEvidence.flatMap((item) => [
        {
          step: `${item.toolName} policy`,
          status: viewText(viewRecord(item.policyDecision), ["status"], item.planStatus),
          rationale:
            item.policyReasons.length > 0
              ? item.policyReasons.join(" ")
              : "Tool policy decision recorded.",
        },
        {
          step: `${item.toolName} result`,
          status: item.resultStatus,
          rationale: item.detail,
        },
      ]),
    ],
    aiDecisionTrail: [],
    messages: threadMessages.map((message) => ({
      id: message.id,
      sender:
        message.sender_type === "customer"
          ? conversation.customer_name
          : message.sender_type === "ai_agent"
            ? "Sagad OS"
            : titleCase(message.sender_type),
      role: titleCase(message.sender_type),
      body: message.body,
      externalMessageId: message.external_message_id,
      provider: message.provider,
      payload: message.payload,
      deliveryStatus: deliveryStatusForAgentStudioMessage(message, conversation),
      createdAt: message.created_at,
      time: new Date(message.created_at).toLocaleTimeString("en-US", {
          hour: "numeric",
          minute: "2-digit",
      }),
    })),
  };
}

function toConversationView(conversation: Conversation): ConversationView {
  const contact = contactById.get(conversation.contactId);
  const agent = conversation.assignedAgentId
    ? agentById.get(conversation.assignedAgentId)
    : undefined;
  const pod = podById.get(conversation.supervisorPodId);
  const lane = laneForConversation(conversation);
  const ageMinutes = minutesBetween(conversation.openedAt);
  const toolAttempts = conversation.toolCallIds.length;
  const riskLevel =
    conversation.langGraphRun.approvalPayload?.riskLevel ??
    (conversation.priority === "urgent"
      ? "high"
      : conversation.classifier.confidence < 0.8
        ? "medium"
        : "low");
  const toolPlans = conversation.toolCallIds.map((toolId) => {
    const tool = toolById.get(toolId);
    const toolName = tool?.name ?? toolId;
    const requiresApproval = tool?.requiresApproval ?? true;
    const policyDecision = {
      allowed: !requiresApproval,
      status: requiresApproval ? "Approval required" : "Allowed",
      requiresApproval,
      approval: requiresApproval ? "Required" : "Not required",
      dryRun: requiresApproval,
      liveMode: requiresApproval ? "Dry-run" : "Live",
      blockedReason: requiresApproval ? "Supervisor approval is required before execution." : "",
      policyReasons: requiresApproval
        ? [
            "Preview fallback keeps write and customer-facing tools approval-gated.",
            "Agent Studio must approve policy before live provider execution.",
          ]
        : ["Preview fallback allows read-only tool use through Agent Studio."],
    };

    return {
      id: `${toolId}-plan`,
      provider: "Agent Studio",
      toolName,
      action: tool?.description ?? "Tool action planned by the orchestration layer.",
      riskLevel: titleCase(requiresApproval ? "medium" : riskLevel),
      requiresApproval,
      approved: false,
      dryRun: requiresApproval,
      args: {
        policy_decision: policyDecision,
      },
      policyDecision,
      policyReasons: policyDecision.policyReasons,
      blockedReason: policyDecision.blockedReason,
      policyStatus: policyDecision.status,
      liveMode: policyDecision.liveMode,
    };
  });
  const toolResults = toolPlans.map((plan) => ({
    id: `${plan.id}-result`,
    planId: plan.id,
    provider: plan.provider,
    toolName: plan.toolName,
    status: plan.requiresApproval ? "Planned" : "Dry Run",
    detail: plan.requiresApproval
      ? "Preview tool plan is waiting on supervisor approval."
      : "Preview read tool is represented as a dry-run result.",
    externalId: null,
    data: {
      policy_decision: plan.policyDecision,
    },
    action: plan.action,
    riskLevel: plan.riskLevel,
    requiresApproval: plan.requiresApproval,
    dryRun: plan.dryRun,
    policyDecision: plan.policyDecision,
    policyReasons: plan.policyReasons,
    blockedReason: plan.blockedReason,
    policyStatus: plan.policyStatus,
    liveMode: plan.liveMode,
  }));
  const toolEvidence = toolPlans.map((plan) => {
    const result = toolResults.find((item) => item.planId === plan.id);
    return {
      id: `${plan.id}-${result?.id ?? "pending"}`,
      planId: plan.id,
      resultId: result?.id ?? "",
      provider: plan.provider,
      toolName: plan.toolName,
      action: plan.action,
      planStatus: plan.policyStatus,
      resultStatus: result?.status ?? "No result",
      detail: result?.detail ?? plan.action,
      riskLevel: plan.riskLevel,
      requiresApproval: plan.requiresApproval,
      approved: plan.approved,
      dryRun: plan.dryRun,
      liveMode: plan.liveMode,
      args: plan.args,
      resultData: result?.data ?? {},
      policyDecision: plan.policyDecision,
      policyReasons: plan.policyReasons,
      blockedReason: plan.blockedReason,
    };
  });
  const policyDecisions = toolEvidence.map((item) => ({
    id: `${item.planId}-policy`,
    toolName: item.toolName,
    status: viewText(viewRecord(item.policyDecision), ["status"], item.planStatus),
    riskLevel: item.riskLevel,
    requiresApproval: item.requiresApproval,
    dryRun: item.dryRun,
    liveMode: item.liveMode,
    blockedReason: item.blockedReason,
    policyReasons: item.policyReasons,
    detail: item.policyReasons.join(" "),
  }));
  const qaFindings = [
    {
      label: "Supervisor approval policy",
      status: conversation.reviewDecision ? "Watch" : "Pass",
      detail: conversation.reviewDecision?.reason ?? "No supervisor approval required in mock state.",
    },
  ];

  return {
    ...conversation,
    customerName: contact?.displayName ?? "Unknown contact",
    contact: contact?.displayName ?? "Unknown contact",
    name: contact?.displayName ?? "Unknown contact",
    source: titleCase(conversation.channel),
    lane,
    queueType: lane,
    queueReason:
      conversation.reviewDecision?.reason ??
      (lane === "Low confidence"
        ? "Sales or support should ask one probing question."
        : conversation.classifier.summary),
    reason:
      conversation.reviewDecision?.reason ??
      (lane === "Failed tool/send"
        ? "CRM or send action needs retry or manual handling."
        : conversation.classifier.summary),
    intent: titleCase(conversation.classifier.intent),
    driver: titleCase(conversation.classifier.intent),
    confidence: percent(conversation.classifier.confidence),
    aiConfidence: percent(conversation.classifier.confidence),
    age: minutesLabel(ageMinutes),
    waitTime: minutesLabel(minutesBetween(conversation.updatedAt)),
    oldestAge: minutesLabel(ageMinutes),
    priority: priorityLabel(conversation.priority),
    severity: titleCase(riskLevel),
    attempts: Math.max(1, toolAttempts),
    toolAttempts,
    status: lane === "Monitoring" ? titleCase(conversation.status) : lane,
    queueStatus: lane,
    summary: conversation.classifier.summary,
    lastMessage: lastCustomerMessage(conversation),
    draftReply: lastAgentDraft(conversation),
    suggestedReply: lastAgentDraft(conversation),
    assignedTo: agent?.name ?? "Unassigned",
    supervisorPod: pod?.name ?? "Unassigned",
    crmContext: contactContext(contact),
    customerContext: contactContext(contact),
    decisionTrail: decisionTrail(conversation),
    aiDecisionTrail: decisionTrail(conversation),
    toolPlans,
    toolResults,
    toolEvidence,
    policyDecisions,
    policyChecks: policyDecisions,
    toolPolicyDecisions: policyDecisions,
    channelProvider: "Mock inbox",
    hitlStatus: conversation.reviewDecision ? "Needs approval" : "Auto-sent",
    sendStatus:
      conversation.messages.some((message) => message.deliveryStatus === "failed")
        ? "Failed"
        : conversation.reviewDecision?.status === "pending"
          ? "Not sent"
          : conversation.messages.some((message) => message.deliveryStatus === "sent")
            ? "Sent"
            : "Drafted",
    complianceStatus: conversation.reviewDecision ? "Needs review" : "Pass",
    knowledgeContext: knowledgeForConversation(conversation),
    qaCompliance: qaFindings,
    qaFindings,
    qa_findings: qaFindings,
    messages: conversation.messages.map((message) => ({
      ...message,
      sender: message.senderName,
      role: titleCase(message.senderType),
      time: new Date(message.createdAt).toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
      }),
    })),
  };
}

function toAgentViews(): AgentView[] {
  return mockAgents.map((agent) => ({
    ...agent,
    role: titleCase(agent.role),
    lane:
      agent.role === "supervisor"
        ? "Supervisor"
        : agent.role === "human_agent"
          ? "Support"
          : "Sales / Support",
    supervisor: "Unassigned",
    podLead: "Unassigned",
    owner: "Unassigned",
    handled: agent.activeConversationCount * 12 + 14,
    resolved: agent.activeConversationCount * 8 + 9,
    volume: agent.activeConversationCount,
    aht: agent.role === "supervisor" ? "n/a" : "4m 18s",
    avgHandleTime: agent.role === "supervisor" ? "n/a" : "4m 18s",
    qaScore: agent.role === "supervisor" ? "n/a" : "92",
    qualityScore: agent.role === "supervisor" ? "n/a" : "92",
    health: titleCase(agent.status),
  }));
}

function toDriverView(driver: ContactDriver): DriverView {
  const ahtByDriver: Record<string, string> = {
    "driver-pricing": "3m 42s",
    "driver-general-intake": "2m 54s",
    "driver-account-support": "5m 08s",
    "driver-tool-failure": "8m 22s",
    "driver-takeover": "12m 40s",
  };
  const escalationPercent =
    driver.priority === "urgent" ? 72 : driver.priority === "high" ? 24 : 12;
  const driverMeta: Record<
    string,
    {
      workstream: string;
      platform: string;
      integration: string;
      csat: string;
      qaScore: string;
      fcr: string;
      costInteraction: string;
    }
  > = {
    "driver-sales-sizing": {
      workstream: "Sales",
      platform: "Chatwoot",
      integration: "Twenty CRM",
      csat: "92%",
      qaScore: "94%",
      fcr: "82%",
      costInteraction: "$0.08",
    },
    "driver-order-status": {
      workstream: "Support",
      platform: "Chatwoot",
      integration: "Markdown KB",
      csat: "88%",
      qaScore: "90%",
      fcr: "74%",
      costInteraction: "$0.04",
    },
    "driver-refund-policy": {
      workstream: "Support",
      platform: "Chatwoot",
      integration: "Twenty CRM",
      csat: "86%",
      qaScore: "91%",
      fcr: "78%",
      costInteraction: "$0.11",
    },
    "driver-tool-failure": {
      workstream: "AI Ops",
      platform: "Agent Studio",
      integration: "Twenty CRM",
      csat: "71%",
      qaScore: "72%",
      fcr: "42%",
      costInteraction: "$0.19",
    },
    "driver-angry-escalation": {
      workstream: "Escalations",
      platform: "Sagad OS",
      integration: "Chatwoot + Twenty",
      csat: "79%",
      qaScore: "81%",
      fcr: "55%",
      costInteraction: "$0.27",
    },
  };
  const meta = driverMeta[driver.id] ?? {
    workstream: "Operations",
    platform: "Sagad OS",
    integration: "Adapter",
    csat: "n/a",
    qaScore: "n/a",
    fcr: "n/a",
    costInteraction: "$0.00",
  };

  return {
    ...driver,
    ...meta,
    name: driver.label,
    driver: driver.label,
    intent: driver.label,
    count: driver.queueCount,
    volume: driver.queueCount,
    contacts: driver.queueCount,
    risk:
      driver.priority === "urgent"
        ? "High"
        : driver.priority === "high"
          ? "Medium"
          : "Normal",
    riskLevel:
      driver.priority === "urgent"
        ? "High"
        : driver.priority === "high"
          ? "Medium"
          : "Normal",
    aht: ahtByDriver[driver.id] ?? "4m 00s",
    avgHandleTime: ahtByDriver[driver.id] ?? "4m 00s",
    escalationRate: `${escalationPercent}%`,
    escalationPercent,
    pattern: driver.description,
    note: driver.description,
  };
}

function toSopView(reference: SopReference): SopView {
  const qaBySop: Record<string, { score: number; flags: number; status: string; note: string }> = {
    "sop-pricing": {
      score: 94,
      flags: 0,
      status: "Pass",
      note: "Keep asking one qualifying question after giving the approved range.",
    },
    "sop-verification": {
      score: 88,
      flags: 1,
      status: "Watch",
      note: "Support replies must ask for invoice ZIP or masked phone before account details.",
    },
    "sop-human-takeover": {
      score: 81,
      flags: 2,
      status: "Review",
      note: "Refund and cancellation language should stay neutral until a supervisor reviews.",
    },
    "sop-tool-failure": {
      score: 72,
      flags: 1,
      status: "Watch",
      note: "Failed CRM writes need one retry and a manual task before promising a booking.",
    },
  };
  const qa = qaBySop[reference.id];

  return {
    ...reference,
    type: reference.section === "Tools" ? "Tool SOP" : "SOP",
    category: reference.section,
    owner: reference.section === "Escalations" ? "Supervisor Ops" : "Ops",
    team: reference.section,
    updatedAt: "June 4, 2026",
    lastUpdated: "June 4, 2026",
    status: qa?.status ?? "Draft",
    health: qa?.status ?? "Draft",
    rubric: `${reference.title} Rubric`,
    score: qa?.score ?? 0,
    adherence: qa?.score ?? 0,
    passRate: qa?.score ?? 0,
    flags: qa?.flags ?? 0,
    policyFlags: qa?.flags ?? 0,
    coachingNote: qa?.note ?? "No QA rubric configured yet.",
    note: qa?.note ?? "No QA rubric configured yet.",
    recommendation: qa?.note ?? "No QA rubric configured yet.",
    sop: reference.title,
    reference: reference.title,
    policy: reference.title,
  };
}

function toToolView(tool: McpTool): ToolView {
  const samplePayload = {
    tool: tool.name,
    args:
      tool.name === "crm.schedule_appointment"
        ? {
            contactId: "contact_123",
            serviceType: "Service request",
            requestedFor: "2026-06-04T10:00:00+08:00",
          }
        : {
            contactId: "contact_123",
            conversationId: "conversation_123",
          },
  };

  return {
    ...tool,
    tool: tool.name,
    system: "Twenty CRM",
    provider: "Agent Studio",
    crm: "Twenty CRM",
    providerStatus: "Twenty external",
    deployment: "External VPS",
    mode: tool.requiresApproval ? "Supervisor gated" : "Server-side read",
    owner: tool.requiresApproval ? "Supervisor Ops" : "Ops",
    team: tool.requiresApproval ? "Supervisor Ops" : "Ops",
    health: titleCase(tool.status),
    samplePayload: JSON.stringify(samplePayload, null, 2),
    payload: JSON.stringify(samplePayload, null, 2),
  };
}


// TODO: Replace with real fetch from Agent Studio once API is available, and remove mockMcpTools from the tool views list.
function previewToolViews(): ToolView[] {
  return [
    {
      id: "tool-chatwoot-webhook",
      name: "chatwoot.webhook.receive",
      label: "Chatwoot inbound webhook",
      description: "Receive live Chatwoot messages into Agent Studio.",
      status: "available",
      requiresApproval: false,
      tool: "chatwoot.webhook.receive",
      system: "Chatwoot",
      provider: "Agent Studio",
      crm: "Chatwoot",
      owner: "AI Ops",
      team: "Agent Studio",
      health: agentStudioBaseUrl() ? "Ready" : "Planned",
      providerStatus: "External channel",
      mode: "Webhook",
      samplePayload: JSON.stringify(
        {
          event: "message_created",
          content: "Hello, I need help.",
          conversation: { id: 42 },
        },
        null,
        2,
      ),
    },
    {
      id: "tool-chatwoot-send-approved",
      name: "chatwoot.messages.send_approved",
      label: "Send approved Chatwoot reply",
      description: "Send a supervisor-approved reply back to Chatwoot.",
      status: "degraded",
      requiresApproval: true,
      tool: "chatwoot.messages.send_approved",
      system: "Chatwoot",
      provider: "Agent Studio",
      crm: "Chatwoot",
      owner: "Supervisor Ops",
      team: "Agent Studio",
      health: "Supervisor approval only",
      providerStatus: "External channel",
      mode: "Approved send only",
      samplePayload: JSON.stringify(
        {
          approved: true,
          supervisor_id: "dev-supervisor",
          edited_reply: "Approved reply body",
        },
        null,
        2,
      ),
    },
    {
      id: "tool-knowledge-retrieve",
      name: "knowledge.retrieve_context",
      label: "Retrieve KB/SOP context",
      description: "Search Markdown knowledge packs with intent and risk filters.",
      status: "available",
      requiresApproval: false,
      tool: "knowledge.retrieve_context",
      system: "Markdown Knowledge Pack",
      provider: "Agent Studio",
      crm: "Knowledge",
      owner: "QA Ops",
      team: "Knowledge Ops",
      health: "Ready",
      providerStatus: "Local source",
      mode: "In-memory retrieval",
      samplePayload: JSON.stringify(
        {
          intent: "general_support",
          risk_level: "low",
          query: "customer needs help",
        },
        null,
        2,
      ),
    },
    {
      id: "tool-twenty-contact-lookup",
      name: "crm.lookup_contact",
      label: "Twenty contact lookup",
      description: "Read contact, company, stage, notes, tasks, and history through Agent Studio.",
      status: "degraded",
      requiresApproval: false,
      tool: "crm.lookup_contact",
      system: "Twenty CRM",
      provider: "Agent Studio",
      crm: "Twenty CRM",
      owner: "Revenue Ops",
      team: "Agent Studio",
      health: "External / dry-run",
      providerStatus: "Twenty external",
      deployment: "Existing VPS",
      mode: "GraphQL read",
      samplePayload: JSON.stringify(
        {
          query: "Riley Chen",
          provider: "twenty",
          source: "agent-studio",
        },
        null,
        2,
      ),
    },
    {
      id: "tool-twenty-create-note",
      name: "crm.create_note",
      label: "Twenty create note",
      description: "Write a supervised CRM note after approval gates pass.",
      status: "degraded",
      requiresApproval: true,
      tool: "crm.create_note",
      system: "Twenty CRM",
      provider: "Agent Studio",
      crm: "Twenty CRM",
      owner: "Supervisor Ops",
      team: "Agent Studio",
      health: "Dry-run",
      providerStatus: "Twenty external",
      deployment: "Existing VPS",
      mode: "Write gated",
      samplePayload: JSON.stringify(
        {
          contact_id: "person_123",
          note: "Supervisor-approved summary",
          approved: true,
          supervisor_id: "demo-supervisor",
        },
        null,
        2,
      ),
    },
    {
      id: "tool-generic-webhook",
      name: "crm.create_task",
      label: "Generic webhook trigger",
      description: "Future provider-neutral webhook handoff governed by Agent Studio.",
      status: "disabled",
      requiresApproval: true,
      tool: "webhook.outbound.trigger",
      system: "Generic Webhooks",
      provider: "Agent Studio",
      crm: "Webhook",
      owner: "AI Ops",
      team: "Platform",
      health: "Planned",
      providerStatus: "External connector",
      deployment: "Provider-neutral",
      mode: "Supervisor-gated webhook",
      samplePayload: JSON.stringify(
        {
          event_type: "post_approval_followup",
          conversation_id: "conv_123",
          approved: true,
        },
        null,
        2,
      ),
    },
    {
      id: "tool-langsmith-trace",
      name: "observability.langsmith.trace",
      label: "LangSmith trace metadata",
      description: "Attach graph, tool, approval, and failure metadata to traces when configured.",
      status: "degraded",
      requiresApproval: false,
      tool: "observability.langsmith.trace",
      system: "LangSmith",
      provider: "Agent Studio",
      crm: "Observability",
      owner: "AI Ops",
      team: "Platform",
      health: "Optional",
      providerStatus: "External observability",
      deployment: "LangSmith cloud",
      mode: "Env telemetry",
      samplePayload: JSON.stringify(
        {
          thread_id: "thread_123",
          approval_status: "needs_approval",
          tool_results: [],
        },
        null,
        2,
      ),
    },
    {
      id: "tool-future-mcp-layer",
      name: "crm.update_lead_stage",
      label: "Future MCP tool layer",
      description: "Provider-neutral tool facade for CRMs, inboxes, knowledge stores, and internal systems.",
      status: "disabled",
      requiresApproval: true,
      tool: "mcp.tool_layer.dispatch",
      system: "MCP",
      provider: "Agent Studio",
      crm: "Tool layer",
      owner: "AI Ops",
      team: "Platform",
      health: "Planned",
      providerStatus: "Future",
      deployment: "Sagad OS",
      mode: "Adapter facade",
      samplePayload: JSON.stringify(
        {
          tool: "crm.notes.create",
          provider: "twenty",
          approval_id: "approval_123",
        },
        null,
        2,
      ),
    },
  ];
}

function policyReasonsForTool(
  row: ViewRecord,
  policyDecision: ViewRecord = {},
): string[] {
  return uniqueStrings([
    ...viewStringArray(row, ["policy_reasons", "policyReasons", "reasons"]),
    ...viewStringArray(policyDecision, [
      "policy_reasons",
      "policyReasons",
      "reasons",
    ]),
  ]);
}

function toToolManifestView(row: ViewRecord): ViewRecord {
  const toolName = viewText(
    row,
    ["tool_name", "toolName", "tool", "name"],
    "unknown.tool",
  );
  const provider = viewText(row, ["provider", "system"], "Agent Studio");
  const skillName = viewText(
    row,
    ["skill_name", "skillName", "skill", "category"],
    "agent-studio",
  );
  const mode = viewText(row, ["mode", "execution_mode", "executionMode"], "read");
  const riskLevel = titleCase(viewText(row, ["risk_level", "riskLevel", "risk"], "medium"));
  const requiresApproval = viewBoolean(row, [
    "requires_approval",
    "requiresApproval",
  ]);
  const enabled = viewBoolean(row, ["enabled"], true);
  const dryRunDefault = viewBoolean(row, [
    "dry_run_default",
    "dryRunDefault",
    "dry_run",
    "dryRun",
  ]);
  const inputSchema = viewNestedRecord(row, ["input_schema", "inputSchema", "schema"]);
  const policyDecision = viewNestedRecord(row, [
    "policy_decision",
    "policyDecision",
  ]);
  const policyReasons = policyReasonsForTool(row, policyDecision);

  return {
    ...row,
    id: viewText(row, ["id"], `tool-${toolName}`),
    name: toolName,
    label: viewText(row, ["label", "display_name", "displayName"], titleCase(toolName)),
    description: viewText(
      row,
      ["description", "detail"],
      `${toolName} is exposed through Agent Studio tool policy.`,
    ),
    tool: toolName,
    toolName,
    provider,
    system: provider,
    skillName,
    mode: titleCase(mode),
    modeRaw: mode,
    risk: riskLevel,
    riskLevel,
    allowedAgents: viewStringArray(row, ["allowed_agents", "allowedAgents"]),
    requiresApproval,
    approval: requiresApproval ? "Required" : "Not required",
    enabled,
    status: enabled ? "Available" : "Disabled",
    health: enabled ? "Available" : "Disabled",
    dryRun: dryRunDefault,
    dryRunDefault,
    liveMode: dryRunDefault ? "Dry-run default" : "Live when policy allows",
    boundary: "Agent Studio server-side adapter",
    policyDecision,
    policyReasons:
      policyReasons.length > 0
        ? policyReasons
        : [
            requiresApproval
              ? "Write or customer-facing tool remains approval-gated."
              : "Read tool remains policy-wrapped by Agent Studio.",
          ],
    inputSchema,
    inputSchemaJson: jsonPreview(inputSchema),
    samplePayload: jsonPreview({ tool: toolName, args: inputSchema }),
    payload: jsonPreview({ tool: toolName, args: inputSchema }),
    source: "agent-studio",
  };
}

function previewToolManifestViews(): ViewRecord[] {
  return [...previewToolViews(), ...mockMcpTools.map(toToolView)].map((tool) =>
    toToolManifestView({
      ...tool,
      tool_name: viewText(tool, ["tool", "name"], "unknown.tool"),
      provider: viewText(tool, ["system", "provider"], "Agent Studio"),
      skill_name: viewText(tool, ["team", "owner"], "agent-studio"),
      mode: viewText(tool, ["mode"], tool.requiresApproval ? "write" : "read"),
      risk_level: tool.requiresApproval ? "medium" : "low",
      requires_approval: tool.requiresApproval,
      enabled: viewText(tool, ["status"], "available") !== "disabled",
      dry_run_default: tool.requiresApproval,
      input_schema: viewRecord(
        tool.requiresApproval
          ? {
              approved: "boolean",
              supervisor_id: "string",
              conversation_id: "string",
            }
          : {
              conversation_id: "string",
              query: "string",
            },
      ),
      policy_reasons: tool.requiresApproval
        ? [
            "Preview fallback keeps write and customer-facing tools approval-gated.",
            "Dry-run remains default until Agent Studio provider writes are enabled.",
          ]
        : ["Preview fallback allows read-only context tools through Agent Studio."],
    }));
}

function toSkillDefinitionView(row: ViewRecord): ViewRecord {
  const name = viewText(row, ["name", "skill_name", "skillName"], "unnamed_skill");
  const riskLevel = titleCase(viewText(row, ["risk_level", "riskLevel", "risk"], "low"));
  const requiresModel = viewBoolean(row, ["requires_model", "requiresModel"]);
  const requiresTools = viewBoolean(row, ["requires_tools", "requiresTools"]);
  const allowedAgents = viewStringArray(row, ["allowed_agents", "allowedAgents", "agents"]);
  const requiredTools = viewStringArray(row, [
    "required_tools",
    "requiredTools",
    "allowed_tools",
    "allowedTools",
    "tools",
  ]);
  const policyReasons = uniqueStrings([
    ...viewStringArray(row, ["policy_reasons", "policyReasons", "approvalRules"]),
    riskLevel === "High"
      ? "High-risk skills stay supervisor-visible and approval-aware."
      : "Skill definition is metadata only; provider tools still pass Agent Studio policy.",
  ]);

  return {
    ...row,
    id: viewText(row, ["id"], `skill-${name}`),
    name,
    label: titleCase(name),
    description: viewText(row, ["description", "detail"], "Agent Studio skill definition."),
    category: titleCase(viewText(row, ["category"], "workflow")),
    status: viewText(row, ["status"], "Active"),
    version: viewText(row, ["version"], "registry"),
    agents: allowedAgents,
    allowedAgents,
    allowedTools: requiredTools,
    requiredTools,
    requiresModel,
    requiresTools,
    requiresApproval: viewBoolean(row, ["requires_approval", "requiresApproval"]),
    risk: riskLevel,
    riskLevel,
    mode: requiresTools
      ? "Tool-aware skill"
      : requiresModel
        ? "Model skill"
        : "Deterministic skill",
    dryRun: false,
    liveMode: requiresTools ? "Tool policy decides dry-run/live" : "No provider execution",
    policyReasons,
    drivers: viewStringArray(row, ["drivers", "triggers", "contact_drivers"]),
    knowledgeDomains: viewStringArray(row, [
      "knowledge_domains",
      "knowledgeDomains",
      "domains",
    ]),
    approvalRules: policyReasons,
    testCases: Number(row.test_cases ?? row.testCases ?? 0),
    source: "agent-studio",
  };
}

function previewSkillDefinitionViews(): ViewRecord[] {
  const defaults: ViewRecord[] = [
    {
      name: "classify_message",
      description: "Normalize inbound text and identify intent, sentiment, language, and operational risk.",
      category: "routing",
      allowed_agents: ["Support Agent", "Sales Agent", "Escalation Agent"],
      requires_model: true,
      requires_tools: false,
      risk_level: "low",
    },
    {
      name: "route_agent",
      description: "Select the operating lane, AI worker, and supervisor pod from driver and risk.",
      category: "routing",
      allowed_agents: ["Sagad Dispatch AI"],
      requires_model: false,
      requires_tools: false,
      risk_level: "low",
    },
    {
      name: "retrieve_knowledge",
      description: "Search approved KB, SOP, QA, compliance, and escalation sources through Agent Studio retrieval.",
      category: "knowledge",
      allowed_agents: ["Support Agent", "Sales Agent", "QA Agent"],
      requires_model: false,
      requires_tools: true,
      risk_level: "low",
      required_tools: ["knowledge.search"],
    },
    {
      name: "summarize_thread",
      description: "Produce concise operational context from prior messages without creating policy.",
      category: "memory",
      allowed_agents: ["Support Agent", "QA Agent"],
      requires_model: true,
      requires_tools: false,
      risk_level: "low",
    },
    {
      name: "plan_tools",
      description: "Propose tool plans that must pass policy before dry-run or live execution.",
      category: "tools",
      allowed_agents: ["Support Agent", "Sales Agent", "Escalation Agent"],
      requires_model: true,
      requires_tools: true,
      risk_level: "medium",
      required_tools: ["tool manifest registry"],
    },
    {
      name: "draft_reply",
      description: "Draft a grounded customer response using selected knowledge and conversation context.",
      category: "drafting",
      allowed_agents: ["Support Agent", "Sales Agent"],
      requires_model: true,
      requires_tools: false,
      risk_level: "medium",
    },
    {
      name: "score_confidence",
      description: "Score grounding, policy safety, risk, and handoff needs before supervisor review.",
      category: "quality",
      allowed_agents: ["QA Agent", "Support Agent"],
      requires_model: true,
      requires_tools: false,
      risk_level: "medium",
    },
    {
      name: "apply_guardrails",
      description: "Apply hard blocks, human-review rules, and policy reasons before send or tool execution.",
      category: "policy",
      allowed_agents: ["QA Agent", "Escalation Agent"],
      requires_model: false,
      requires_tools: false,
      risk_level: "high",
    },
    {
      name: "create_approval_item",
      description: "Create the supervisor approval record for risky replies, write tools, or blocked policy paths.",
      category: "approval",
      allowed_agents: ["Sagad Dispatch AI", "Escalation Agent"],
      requires_model: false,
      requires_tools: true,
      risk_level: "high",
      required_tools: ["approval queue"],
      requires_approval: true,
    },
  ];

  return defaults.map(toSkillDefinitionView);
}

function toMcpDescriptorView(row: ViewRecord): ViewRecord {
  const name = viewText(row, ["name", "tool_name", "toolName"], "unknown.tool");
  const mode = viewText(row, ["mode", "execution_mode", "executionMode"], "read");
  const riskLevel = titleCase(viewText(row, ["risk_level", "riskLevel", "risk"], "low"));
  const requiresApproval = viewBoolean(row, [
    "requires_approval",
    "requiresApproval",
  ]);
  const dryRunDefault = viewBoolean(row, [
    "dry_run_default",
    "dryRunDefault",
    "dry_run",
    "dryRun",
  ]);
  const enabled = viewBoolean(row, ["enabled"], true);
  const policyWrapped = viewBoolean(row, [
    "policy_wrapped",
    "policyWrapped",
  ], true);
  const inputSchema = viewNestedRecord(row, ["input_schema", "inputSchema", "schema"]);
  const policyReasons = uniqueStrings([
    ...viewStringArray(row, ["policy_reasons", "policyReasons", "reasons"]),
    policyWrapped
      ? "Descriptor exposes only the Agent Studio policy-wrapped tool contract."
      : "Descriptor is not policy-wrapped and should remain hidden from execution.",
  ]);

  return {
    ...row,
    id: viewText(row, ["id"], `mcp-${name}`),
    name,
    title: name,
    description: viewText(
      row,
      ["description", "detail"],
      "Descriptor-only MCP boundary generated by Agent Studio.",
    ),
    detail: viewText(
      row,
      ["detail", "description"],
      "Descriptor only. Browser code never calls MCP servers or provider APIs directly.",
    ),
    transport: viewText(row, ["transport"], "descriptor"),
    status: enabled ? "Descriptor ready" : "Disabled",
    enabled,
    policyWrapped,
    mode: titleCase(mode),
    modeRaw: mode,
    risk: riskLevel,
    riskLevel,
    requiresApproval,
    approval: requiresApproval ? "Required" : "Not required",
    dryRun: dryRunDefault,
    dryRunDefault,
    liveMode: dryRunDefault ? "Dry-run default" : "Live when policy allows",
    boundary: viewText(
      row,
      ["boundary"],
      "MCP descriptor -> Agent Studio tool policy -> provider adapter",
    ),
    trustLevel: policyWrapped ? "Policy-wrapped" : "Descriptor only",
    toolsCount: 1,
    resourcesCount: Number(row.resources_count ?? row.resourcesCount ?? 0),
    promptsCount: Number(row.prompts_count ?? row.promptsCount ?? 0),
    tools: [name],
    allowedAgents: viewStringArray(row, ["allowed_agents", "allowedAgents"]),
    allowedSkills: viewStringArray(row, ["allowed_skills", "allowedSkills", "skill_name", "skillName"]),
    policyReasons,
    inputSchema,
    inputSchemaJson: jsonPreview(inputSchema),
    source: "agent-studio",
  };
}

function previewMcpDescriptorViews(): ViewRecord[] {
  return previewToolManifestViews()
    .filter((tool) => viewBoolean(tool, ["enabled"], true))
    .map((tool) =>
      toMcpDescriptorView({
        name: viewText(tool, ["toolName", "tool", "name"], "unknown.tool"),
        description: viewText(tool, ["description"], ""),
        mode: viewText(tool, ["modeRaw", "mode"], "read"),
        risk_level: viewText(tool, ["riskLevel", "risk"], "low").toLowerCase(),
        requires_approval: viewBoolean(tool, ["requiresApproval"]),
        dry_run_default: viewBoolean(tool, ["dryRunDefault", "dryRun"]),
        enabled: true,
        policy_wrapped: true,
        input_schema: viewNestedRecord(tool, ["inputSchema", "input_schema"]),
        policy_reasons: viewStringArray(tool, ["policyReasons", "policy_reasons"]),
        skill_name: viewText(tool, ["skillName"], "agent-studio"),
      }),
    );
}

// TODO: Replace with real fetch from Agent Studio once API is available, and remove mockConversations from the lane and queue health lists.
function queueHealth(conversations: ConversationView[]): ViewRecord[] {
  if (conversations.length === 0) {
    return [];
  }

  return ["Sales", "Support", "Refunds", "Escalations"].map((queue) => {
    const rows = conversations.filter(
      (conversation) =>
        String(conversation.driver).includes(queue) ||
        String(conversation.lane).includes(queue) ||
        (queue === "Refunds" &&
          String(conversation.driver).toLowerCase().includes("refund")) ||
        (queue === "Escalations" &&
          ["Escalated", "Failed tool/send"].includes(String(conversation.lane))) ||
        routeForIntent(conversation.classifier.intent) === queue,
    );
    const averageConfidence =
      rows.reduce((sum, row) => sum + row.classifier.confidence, 0) /
      Math.max(1, rows.length);
    const oldest = rows.reduce(
      (max, row) => Math.max(max, minutesBetween(row.openedAt)),
      0,
    );
    const hasRisk = rows.some((row) => row.priority === "High risk");

    return {
      queue,
      name: queue,
      lane: queue,
      backlog: rows.length,
      open: rows.length,
      count: rows.length,
      oldestAge: minutesLabel(oldest),
      oldest: minutesLabel(oldest),
      age: minutesLabel(oldest),
      confidence: percent(averageConfidence),
      avgConfidence: percent(averageConfidence),
      health: hasRisk ? "At risk" : rows.length > 0 ? "Healthy" : "Idle",
      status: hasRisk ? "At risk" : rows.length > 0 ? "Healthy" : "Idle",
    };
  });
}

// TODO: Replace with real fetch from Agent Studio once API is available, and remove mockConversations from the channel health list.
function channelHealth(conversations: ConversationView[], source: string): ViewRecord[] {
  const chatwootCount = conversations.filter(
    (conversation) => conversation.channelProvider === "Chatwoot",
  ).length;
  const knowledgeCount = conversations.filter((conversation) =>
    Array.isArray(conversation.knowledgeContext),
  ).length;
  const hitlCount = conversations.filter((conversation) =>
    String(conversation.hitlStatus).toLowerCase().includes("approval"),
  ).length;

  return [
    {
      channel: "Chatwoot",
      status: source === "agent-studio" ? "Live adapter" : "Mock fallback",
      volume: chatwootCount,
      detail: source === "agent-studio" ? "Reading Agent Studio conversations" : "No SAGAD_API_BASE_URL configured",
    },
    {
      channel: "Knowledge Pack",
      status: "Ready",
      volume: knowledgeCount,
      detail: "KB/SOP/QA/compliance context visible in review",
    },
    {
      channel: "Approved Send",
      status: "Gated",
      volume: hitlCount,
      detail: "Approved-send required before outbound Chatwoot reply",
    },
    {
      channel: "LangSmith",
      status: "Optional",
      volume: 0,
      detail: "Trace links appear when Agent Studio is configured",
    },
  ];
}

function attentionSummary(conversations: ConversationView[]): ViewRecord[] {
  if (conversations.length === 0) {
    return [];
  }

  // TODO: Replace with real fetch from Agent Studio once API is available, and remove mockConversations from the attention summary list.
  const groups = ["Approval", "Low confidence", "Escalated", "Failed tool/send"];

  return groups.map((group) => {
    const rows = conversations.filter((conversation) => conversation.lane === group);
    return {
      type: group,
      category: group,
      reason: group,
      count: rows.length,
      total: rows.length,
      items: rows.length,
      owner: "Sagad AI Ops Pod",
      team: "Sagad AI Ops Pod",
      pod: "Sagad AI Ops Pod",
      severity:
        group === "Failed tool/send" || group === "Escalated"
          ? "High risk"
          : group === "Low confidence"
            ? "Review"
            : "Pending",
      status:
        group === "Failed tool/send" || group === "Escalated"
          ? "High risk"
          : group === "Low confidence"
            ? "Review"
            : "Pending",
    };
  });
}

function supervisorPodViews(): ViewRecord[] {
  return mockSupervisorPods.map((pod) => {
    const lead = agentById.get(pod.leadSupervisorId);
    return {
      ...pod,
      lead: lead?.name ?? "Unassigned",
      supervisor: lead?.name ?? "Unassigned",
      load: pod.openConversationCount,
      active: pod.openConversationCount,
      open: pod.openConversationCount,
      status: pod.slaRiskCount > 0 ? "Watch" : "Healthy",
      health: pod.slaRiskCount > 0 ? "Watch" : "Healthy",
    };
  });
}

function isSentStatus(value: unknown): boolean {
  const normalized = String(value ?? "")
    .toLowerCase()
    .replaceAll("_", " ");

  return normalized === "sent" || normalized === "delivered";
}

// TODO: Replace with real fetch from Agent Studio once API is available, and remove mockConversations from the dashboard data.
export async function getDashboardData(): Promise<DashboardViewData> {
  const liveConversations = await fetchAgentStudioConversations();
  const source = liveConversations ? "agent-studio" : "mock";
  const conversations =
    liveConversations?.map(toAgentStudioConversationView) ??
    mockConversations.map(toConversationView);
  const approvalConversations = conversations.filter((conversation) =>
    ["Approval", "Escalated", "Failed tool/send", "Low confidence"].includes(
      String(conversation.lane),
    ),
  );
  const highRiskConversations = conversations.filter(
    (conversation) => conversation.priority === "High risk",
  );
  const isDemoSeed = source === "mock";

  return clone({
    ...homeServicesDashboardData,
    conversations,
    agents: toAgentViews(),
    supervisorPods: supervisorPodViews(),
    contactDrivers: mockContactDrivers.map(toDriverView),
    sopReferences: mockSopReferences.map(toSopView),
    mcpTools: mockMcpTools.map(toToolView),
    accountName: homeServicesDashboardData.account.name,
    lastUpdated: "June 4, 2026 9:00 AM",
    asOf: "June 4, 2026 9:00 AM",
    metrics: {
      messagesReceived: isDemoSeed ? 128 : conversations.length,
      totalConversations: isDemoSeed ? 128 : conversations.length,
      aiDraftedResponses: isDemoSeed ? 91 : conversations.length,
      aiDrafted: isDemoSeed ? 91 : conversations.length,
      autoSentResponses: isDemoSeed ? 42 : conversations.filter((conversation) =>
        isSentStatus(conversation.sendStatus),
      ).length,
      autoSent: isDemoSeed ? 42 : conversations.filter((conversation) =>
        isSentStatus(conversation.sendStatus),
      ).length,
      approvalRequired: isDemoSeed ? 31 : approvalConversations.length,
      needsApproval: isDemoSeed ? 31 : approvalConversations.length,
      approved: isDemoSeed ? 23 : conversations.filter((conversation) =>
        String(conversation.hitlStatus).toLowerCase().includes("approved"),
      ).length,
      edited: isDemoSeed ? 6 : 0,
      rejected: isDemoSeed ? 10 : conversations.filter((conversation) =>
        String(conversation.hitlStatus).toLowerCase().includes("rejected"),
      ).length,
      escalated: isDemoSeed ? 8 : conversations.filter(
        (conversation) => conversation.lane === "Escalated",
      ).length,
      averageConfidence: isDemoSeed ? "86%" : percent(
        conversations.reduce((sum, row) => sum + row.classifier.confidence, 0) /
          Math.max(1, conversations.length),
      ),
      topMissingKnowledgeTopics: ["Refund policy unclear for sale items"],
      topIssue: "Refund policy unclear for sale items",
      recommendedAction: "Add SOP rule for sale-item refund exceptions.",
      openQueue: conversations.length,
      openItems: conversations.length,
      queueCount: conversations.length,
      slaRisk: highRiskConversations.length,
      slaBreaches: highRiskConversations.length,
      atRisk: highRiskConversations.length,
      approvalLoad: approvalConversations.length,
      pendingApprovals: approvalConversations.length,
      podsStaffed: mockSupervisorPods.length,
      activePods: mockSupervisorPods.length,
    },
    attentionSummary: attentionSummary(conversations),
    attentionItems: attentionSummary(conversations),
    queueHealth: queueHealth(conversations),
    activeQueues: queueHealth(conversations),
    channelHealth: channelHealth(conversations, source),
    integrationSource: source,
  });
}

export async function getConversations(): Promise<ConversationView[]> {
  const liveConversations = await fetchAgentStudioConversations();
  return clone(
    liveConversations?.map(toAgentStudioConversationView) ??
      mockConversations.map(toConversationView),
  );
}

export async function getQueueConversations(): Promise<ConversationView[]> {
  const liveConversations = await fetchAgentStudioConversations();
  if (liveConversations) {
    return clone(liveConversations.map(toAgentStudioConversationView));
  }

  return clone(
    mockConversations
      .map(toConversationView)
      .filter((conversation) => conversation.status !== "Resolved"),
  );
}

export async function getPrimaryConversation(): Promise<ConversationView> {
  const liveConversations = await fetchAgentStudioConversations();
  if (liveConversations && liveConversations.length > 0) {
    return clone(toAgentStudioConversationView(liveConversations[0]));
  }

  const primaryConversation =
    mockConversations.find(
      (conversation) =>
        conversation.status === "needs_review" &&
        conversation.reviewDecision?.status === "pending",
    ) ??
    mockConversations.find((conversation) => conversation.priority === "urgent") ??
    mockConversations[0];

  return primaryConversation
    ? clone(toConversationView(primaryConversation))
    : clone({} as ConversationView);
}

export async function getAgents(): Promise<AgentView[]> {
  return clone(toAgentViews());
}

export async function getSupervisorPods(): Promise<ViewRecord[]> {
  return clone(supervisorPodViews());
}

export async function getContactDrivers(): Promise<DriverView[]> {
  return clone(mockContactDrivers.map(toDriverView));
}

export async function getSopReferences(): Promise<SopView[]> {
  return clone(mockSopReferences.map(toSopView));
}

export async function getCustomers(): Promise<ViewRecord[]> {
  const conversations = await getConversations();

  return clone(
    mockContacts.map((contact) => {
      const relatedConversations = conversations.filter(
        (conversation) => String(conversation.contactId) === contact.id,
      );
      const openTasks = contact.tasks.filter((task) => task.status === "open");
      const lastConversation = relatedConversations[0];

      return {
        id: contact.id,
        name: contact.displayName,
        customerName: contact.displayName,
        phoneMasked: contact.phoneMasked,
        emailMasked: contact.emailMasked ?? "Not provided",
        city: contact.city,
        stage: titleCase(contact.leadStage),
        leadStage: titleCase(contact.leadStage),
        tags: contact.tags,
        notes: contact.notes,
        tasks: contact.tasks,
        openTasks: openTasks.length,
        serviceHistory: contact.serviceHistory,
        lastService:
          contact.serviceHistory[0]?.serviceType ??
          contact.appointments[0]?.serviceType ??
          "No service history",
        risk: contact.tags.includes("human-takeover")
          ? "High"
          : contact.tags.includes("refund")
            ? "Review"
            : "Normal",
        conversations: relatedConversations.length,
        lastConversationStatus: lastConversation?.queueStatus ?? "No active conversation",
        lastConversationSummary:
          lastConversation?.summary ?? contact.notes[0] ?? "No current notes",
        owner: openTasks[0]?.ownerId
          ? (agentById.get(openTasks[0].ownerId)?.name ?? "Ops")
          : "Ops",
      };
    }),
  );
}

export async function getAuditEvents(): Promise<ViewRecord[]> {
  const conversations = await getConversations();

  return clone(
    conversations.flatMap((conversation) => {
      const trailEvents = viewRecordArray(conversation, [
        "decisionTrail",
        "aiDecisionTrail",
      ]).map((event, index) => ({
          id: `${String(conversation.id)}-${index}`,
          conversationId: conversation.id,
          customerName: conversation.customerName,
          event:
            viewText(event, ["step", "label", "type"], "Audit event") ||
            "Audit event",
          status: viewText(event, ["status", "result"], "Logged"),
          actor: viewText(event, ["actor"], "SagadOS"),
          detail: viewText(event, ["rationale", "detail", "description"], ""),
          createdAt:
            viewText(event, ["createdAt", "time", "timestamp"], "") ||
            viewText(conversation, ["updatedAt", "openedAt"], ""),
        }));
      const sendStatus = viewText(conversation, ["sendStatus"], "");
      const queueStatus = viewText(conversation, ["queueStatus", "status"], "");
      const synthesizedEvents: ViewRecord[] = [
        {
          id: `${String(conversation.id)}-draft-created`,
          conversationId: conversation.id,
          customerName: conversation.customerName,
          event: "AI draft created",
          status: viewText(conversation, ["confidence", "aiConfidence"], "Drafted"),
          actor: "Sagad agents",
          detail: viewText(conversation, ["draftReply", "suggestedReply"], "Draft generated for supervisor review."),
          createdAt: viewText(conversation, ["updatedAt", "openedAt"], ""),
        },
      ];

      if (queueStatus.toLowerCase().includes("approval")) {
        synthesizedEvents.push({
          id: `${String(conversation.id)}-approval-requested`,
          conversationId: conversation.id,
          customerName: conversation.customerName,
          event: "Approval requested",
          status: queueStatus,
          actor: "Sagad approvals",
          detail: viewText(conversation, ["reason", "queueReason"], "Supervisor approval required."),
          createdAt: viewText(conversation, ["updatedAt", "openedAt"], ""),
        });
      }

      if (isSentStatus(sendStatus)) {
        synthesizedEvents.push({
          id: `${String(conversation.id)}-reply-sent`,
          conversationId: conversation.id,
          customerName: conversation.customerName,
          event: "Reply sent",
          status: "Sent",
          actor: "Sagad audit",
          detail: "Final customer response delivery was recorded.",
          createdAt: viewText(conversation, ["updatedAt", "openedAt"], ""),
        });
      }

      if (queueStatus.toLowerCase().includes("escal")) {
        synthesizedEvents.push({
          id: `${String(conversation.id)}-escalation-created`,
          conversationId: conversation.id,
          customerName: conversation.customerName,
          event: "Escalation created",
          status: queueStatus,
          actor: "Supervisor",
          detail: viewText(conversation, ["reason", "summary"], "Conversation escalated to a human supervisor."),
          createdAt: viewText(conversation, ["updatedAt", "openedAt"], ""),
        });
      }

      for (const toolResult of viewRecordArray(conversation, ["toolResults", "deliveryResults"])) {
        synthesizedEvents.push({
          id: `${String(conversation.id)}-${viewText(toolResult, ["id", "toolName"], "tool")}`,
          conversationId: conversation.id,
          customerName: conversation.customerName,
          event: "Tool called",
          status: viewText(toolResult, ["status"], "Logged"),
          actor: viewText(toolResult, ["provider"], "Agent Studio"),
          detail: viewText(toolResult, ["detail"], "Tool result recorded."),
          createdAt: viewText(conversation, ["updatedAt", "openedAt"], ""),
        });
      }

      return [...trailEvents, ...synthesizedEvents];
    }),
  );
}

export async function getKnowledgeIngestionOverview(): Promise<ViewRecord> {
  const [documentResult, jobResult, sourceResult] = await Promise.all([
    fetchAgentStudioKnowledgeDocuments(),
    fetchAgentStudioKnowledgeJobs(),
    fetchAgentStudioKnowledgeSources(),
  ]);
  const connectionStatus = summarizeAgentStudioStatus([
    documentResult,
    jobResult,
    sourceResult,
  ]);
  const liveDocuments = documentResult.data;
  const liveJobs = jobResult.data;
  const liveSources = sourceResult.data;
  const sourceDetail =
    [documentResult, jobResult, sourceResult].find((result) => result.detail)?.detail ??
    null;
  const documents =
    liveDocuments?.map((document) => ({
      id: document.id,
      sourceId: document.source_id,
      title: document.title,
      category: titleCase(document.category),
      type: titleCase(document.category),
      sourcePath: document.source_path,
      source: document.pack_slug,
      owner: "Knowledge Ops",
      status: titleCase(document.approval_status),
      approvalStatus: document.approval_status,
      version: document.version,
      chunks: document.chunk_count,
      summary: document.content.slice(0, 180),
      content: document.content,
      contentHash: document.content_hash,
      jobId: document.job_id,
      lastEmbeddedAt:
        document.last_embedded_at ??
        viewText(document.metadata, ["last_embedded_at", "lastEmbeddedAt"], document.updated_at),
      updatedAt: document.updated_at,
      createdAt: document.created_at,
      metadata: document.metadata,
    })) ?? mockSopReferences.map(toSopView);

  const jobs =
    liveJobs?.map((job) => ({
      id: job.id,
      source: job.source_name,
      sourceType: titleCase(job.source_type),
      status: titleCase(job.status),
      processed: job.processed_files,
      failed: job.failed_files,
      total: job.total_files,
      summary: job.summary,
      updatedAt: job.updated_at,
      createdAt: job.created_at,
      sourceId: job.source_id,
      errors: job.errors,
      metadata: job.metadata,
    })) ?? [
      {
        id: "demo-job-local-files",
        source: "Manual Upload",
        sourceType: "Local Files",
        status: "Needs Review",
        processed: 3,
        failed: 0,
        total: 3,
        summary: "Demo SOP, refund policy, and shipping FAQ are waiting for review.",
        updatedAt: demoNow,
        errors: [],
      },
    ];

  const plannedSources = [
    {
      id: "planned-google-drive",
      name: "Google Drive",
      type: "Cloud source",
      status: "Planned",
      sync: "24h planned",
      detail: "Future source adapter behind Agent Studio; not browser-direct.",
      lastSyncedAt: null,
      metadata: {},
      planned: true,
    },
    {
      id: "planned-websites",
      name: "Websites",
      type: "Public URLs",
      status: "Planned",
      sync: "Weekly planned",
      detail: "Future public source adapter with manual refresh.",
      lastSyncedAt: null,
      metadata: {},
      planned: true,
    },
    {
      id: "planned-notion",
      name: "Notion / Confluence / Guru",
      type: "Internal KB",
      status: "Planned",
      sync: "24h planned",
      detail: "Future internal source adapters after local ingestion is stable.",
      lastSyncedAt: null,
      metadata: {},
      planned: true,
    },
  ];

  const liveSourceRows =
    liveSources?.map((source) => ({
      id: source.id,
      name: source.name,
      type: titleCase(source.source_type),
      status: titleCase(source.status),
      sync: titleCase(source.sync_policy),
      detail: "Stored by Agent Studio; local re-sync is available for uploaded and extracted content.",
      lastSyncedAt: source.last_synced_at,
      updatedAt: source.updated_at,
      createdAt: source.created_at,
      metadata: source.metadata,
      planned: false,
    })) ?? [
      {
        id: "demo-manual-uploads",
        name: "Manual Uploads",
        type: "Files",
        status: "Ready",
        sync: "Manual",
        detail: "MD, TXT, PDF, DOCX, XLSX, CSV, and transcripts through Agent Studio.",
        lastSyncedAt: null,
        metadata: {},
        planned: false,
      },
      {
        id: "demo-markdown-packs",
        name: "Markdown Knowledge Packs",
        type: "Local source",
        status: "Ready",
        sync: "Manual re-index",
        detail: "Seed KB, SOP, QA, compliance, escalation, and template records.",
        lastSyncedAt: null,
        metadata: {},
        planned: false,
      },
    ];

  const sources = [...liveSourceRows, ...plannedSources];

  return clone({
    documents,
    jobs,
    sources,
    missingKnowledge: [
      {
        topic: "Sale-item refund exceptions",
        count: 7,
        severity: "High",
        recommendedAction: "Add or approve a SOP rule for sale-item refund handling.",
      },
      {
        topic: "Warranty proof requirements",
        count: 4,
        severity: "Medium",
        recommendedAction: "Upload warranty verification script and approve for Support Agent.",
      },
    ],
    agentStudioBaseUrl: agentStudioBaseUrl(),
    connectionDetail: sourceDetail,
    connectionStatus,
    source: connectionStatus === "connected" ? "agent-studio" : "mock",
  });
}

export async function getSopRefs(): Promise<SopView[]> {
  return getSopReferences();
}

export async function getMcpTools(): Promise<ViewRecord[]> {
  const result = await fetchAgentStudioToolManifests();
  const rows =
    result.data?.map(toToolManifestView) ?? previewToolManifestViews();

  return clone(
    rows.map((row) => ({
      ...row,
      connectionStatus: result.status,
      connectionDetail: result.detail ?? null,
      source: result.status === "connected" ? "agent-studio" : "preview",
    })),
  );
}

export async function getSkills(): Promise<ViewRecord[]> {
  const result = await fetchAgentStudioSkills();
  const rows =
    result.data?.map(toSkillDefinitionView) ?? previewSkillDefinitionViews();

  return clone(
    rows.map((row) => ({
      ...row,
      connectionStatus: result.status,
      connectionDetail: result.detail ?? null,
      source: result.status === "connected" ? "agent-studio" : "preview",
    })),
  );
}

export async function getGraphs(): Promise<ViewRecord[]> {
  return clone([
    {
      id: "graph-support-default",
      name: "Default Support Graph",
      description: "Routes inbound service work through context, tools, policy, HITL, send, audit, and trace.",
      status: "Active",
      version: "v0.1.4",
      trigger: "inbound.customer_message",
      nodes: [
        "Classify",
        "CRM Lookup",
        "Knowledge Retrieval",
        "Agent + Skill Selection",
        "Draft",
        "QA Gate",
        "HITL Approval",
        "Send",
        "Audit",
      ],
      hitlPausePoints: ["QA Gate", "HITL Approval", "Failed Tool"],
      allowedAgents: ["Support Agent", "Sales Agent", "Escalation Agent"],
      allowedTools: ["crm.lookup_contact", "knowledge.search", "chatwoot.draft_reply", "chatwoot.send_message"],
      retryPolicy: "Retry read tools once, then route to supervisor.",
      fallbackPath: "Escalate to human takeover with audit event.",
    },
    {
      id: "graph-sales-default",
      name: "Sales Qualification Graph",
      description: "Qualifies buying intent, retrieves sizing context, drafts next question, and gates discounts.",
      status: "Draft",
      version: "v0.2.0",
      trigger: "driver.sales_sizing",
      nodes: ["Classify", "CRM Lookup", "Sizing Retrieval", "Sales Agent", "Draft", "Policy Gate", "Audit"],
      hitlPausePoints: ["Discount Request", "Policy Gate"],
      allowedAgents: ["Sales Agent"],
      allowedTools: ["crm.lookup_contact", "knowledge.search", "chatwoot.draft_reply"],
      retryPolicy: "No write retries in preview.",
      fallbackPath: "Ask clarifying question.",
    },
  ]);
}

export async function getMcpServers(): Promise<ViewRecord[]> {
  const result = await fetchAgentStudioMcpDescriptors();
  const rows =
    result.data?.map(toMcpDescriptorView) ?? previewMcpDescriptorViews();

  return clone(
    rows.map((row) => ({
      ...row,
      connectionStatus: result.status,
      connectionDetail: result.detail ?? null,
      source: result.status === "connected" ? "agent-studio" : "preview",
    })),
  );
}

export async function getAgentRunTraces(): Promise<ViewRecord[]> {
  const conversations = await getConversations();

  return clone(
    conversations.map((conversation, index) => ({
      id: `run-${String(conversation.id)}`,
      conversationId: conversation.id,
      customerName: conversation.customerName,
      agent: conversation.assignedTo ?? "Support Agent",
      skill: String(conversation.driver ?? "").toLowerCase().includes("refund")
        ? "Refund Resolver"
        : String(conversation.driver ?? "").toLowerCase().includes("sales")
          ? "Sales Sizing Assistant"
          : "Order Status Lookup",
      graph: "Default Support Graph v0.1.4",
      driver: conversation.driver,
      status: conversation.queueStatus ?? "Needs Approval",
      trust: conversation.confidence ?? conversation.aiConfidence ?? "72%",
      risk: conversation.priority ?? "Medium",
      langSmithTraceId: conversation.traceUrl ? `ls-${String(conversation.id).slice(-8)}` : "Preview trace",
      traceUrl: conversation.traceUrl ?? "",
      latency: `${(6.8 + index * 0.7).toFixed(1)}s`,
      tokens: 1800 + index * 230,
      estimatedCost: `$${(0.04 + index * 0.01).toFixed(2)}`,
      toolsCalled: ["crm.lookup_contact", "knowledge.search", "chatwoot.draft_reply"],
      mcpServersUsed: index % 2 === 0 ? [] : ["Google Drive MCP"],
      errorSummary: String(conversation.queueStatus ?? "").toLowerCase().includes("failed")
        ? "Provider delivery failed after approval."
        : "",
      startedAt: conversation.openedAt,
    })),
  );
}

export async function getEvaluations(): Promise<ViewRecord[]> {
  const conversations = await getConversations();

  return clone([
    {
      id: "eval-policy-gates",
      name: "Policy Gate Coverage",
      status: "Needs Review",
      score: "82%",
      sampleSize: conversations.length,
      focus: "Approval rules, risk gates, and unclear SOP handling.",
      failures: conversations.filter((row) =>
        String(row.queueStatus).toLowerCase().includes("approval"),
      ).length,
      recommendation: "Add sale-item refund exception tests and require QA approval before auto-send.",
    },
    {
      id: "eval-tool-reliability",
      name: "Tool Reliability",
      status: "Preview",
      score: "91%",
      sampleSize: conversations.length,
      focus: "CRM lookup, knowledge retrieval, and provider delivery results.",
      failures: conversations.filter((row) =>
        String(row.queueStatus).toLowerCase().includes("failed"),
      ).length,
      recommendation: "Keep write/send tools approval-gated and retry read tools once before escalation.",
    },
    {
      id: "eval-tone-safety",
      name: "Brand Tone Safety",
      status: "Healthy",
      score: "94%",
      sampleSize: conversations.length,
      focus: "Empathy, no over-promising, no policy hallucination.",
      failures: 0,
      recommendation: "Maintain supervisor review for angry-customer escalation skill.",
    },
  ]);
}

export async function getIntegrationHealth(): Promise<ViewRecord[]> {
  const connections = await getIntegrationConnections();
  const modelGatewayStatus = await getModelGatewayStatus();
  const connectionRows = connections.map((row) => ({
    ...row,
    entityKind: "adapter",
    visibilityStatus: String(row.status ?? "").toLowerCase().includes("ready")
      ? "Connected"
      : "Preview",
    access: String(row.api_mode ?? "").toLowerCase().includes("read")
      ? "Read-only"
      : "Approval-gated",
    source: "Agent Studio proxy",
    boundary: "Server-side",
  }));

  return clone([
    ...connectionRows,
    {
      id: "health-markdown-knowledge",
      name: "Markdown Knowledge Packs",
      entityKind: "knowledge_source",
      kind: "Knowledge",
      status: "Preview",
      visibilityStatus: "Preview",
      mode: "Local ingestion",
      access: "Read-only retrieval",
      source: "Agent Studio",
      boundary: "Server-side",
      detail: "Approved knowledge is retrievable by agents; writes require Knowledge review.",
    },
    {
      id: "health-langsmith",
      name: "LangSmith",
      entityKind: "service",
      kind: "Observability",
      status: "Missing env",
      visibilityStatus: "Missing env",
      mode: "Optional",
      access: "Trace metadata",
      source: "Agent Studio",
      boundary: "Server-side",
      detail: "Trace links appear when LangSmith environment variables are configured.",
    },
    {
      id: "health-litellm",
      name: "LiteLLM",
      entityKind: "service",
      kind: "Model gateway",
      status: viewText(modelGatewayStatus, ["status"], "agent_studio_unavailable"),
      visibilityStatus: viewText(modelGatewayStatus, ["agentStudioStatus"], "unreachable"),
      mode: "Server-side model routing",
      access: "No browser credentials",
      source: "Agent Studio",
      boundary: "Server-side",
      detail: viewText(modelGatewayStatus, ["detail"], "Provider routing and credentials remain outside the browser."),
    },
    {
      id: "health-generic-webhooks",
      name: "Generic Webhooks",
      entityKind: "adapter",
      kind: "Workflow",
      status: "Planned",
      visibilityStatus: "Planned",
      mode: "Approval-gated writes",
      access: "Disabled in preview",
      source: "Roadmap",
      boundary: "Server-side",
      detail: "Future provider-neutral webhook handoff governed by Agent Studio.",
    },
    {
      id: "health-mcp-fastmcp",
      name: "MCP / FastMCP",
      entityKind: "mcp_server",
      kind: "Capability server",
      status: "Planned",
      visibilityStatus: "Planned",
      mode: "External tool/resource provider",
      access: "Disabled in preview",
      source: "Roadmap",
      boundary: "Server-side",
      detail: "MCP servers are shown for roadmap visibility and are not called from browser code.",
    },
  ]);
}

export async function getModelGatewayStatus(): Promise<ViewRecord> {
  const result = await fetchAgentStudioLiteLlmHealth();
  const payload = result.data ?? {};
  const baseUrl = agentStudioBaseUrl();
  const connected = result.status === "connected";

  return clone({
    id: "model-gateway-litellm",
    name: viewText(payload, ["provider"], "LiteLLM Gateway"),
    agentStudioBaseUrl: baseUrl,
    agentStudioStatus: result.status,
    baseUrl: viewText(payload, ["base_url", "baseUrl"], "http://127.0.0.1:4000/v1"),
    boundary: "Agent Studio server-side only",
    detail: connected
      ? viewText(payload, ["detail"], "LiteLLM status is reported by Agent Studio.")
      : result.status === "not_configured"
        ? "Set SAGAD_API_BASE_URL so the console can ask Agent Studio for model gateway status."
        : result.status === "unauthorized"
          ? "Agent Studio rejected the console request. Check AGENT_STUDIO_INTERNAL_SECRET and session headers."
          : `Agent Studio is not reachable at ${baseUrl ?? "the configured URL"}. Start Agent Studio on port 8010.`,
    dryRun: connected ? Boolean(payload.dry_run) : true,
    external: false,
    mode: viewText(payload, ["mode"], "OpenAI-compatible /v1 model gateway"),
    provider: viewText(payload, ["provider"], "LiteLLM Gateway"),
    setupCommand: "docker compose -f compose.preview.yaml --profile litellm up -d litellm",
    status: connected
      ? viewText(payload, ["status"], "unknown")
      : result.status === "not_configured"
        ? "agent_studio_not_configured"
        : result.status === "unauthorized"
          ? "unauthorized"
          : "agent_studio_unavailable",
    writesEnabled: connected ? Boolean(payload.writes_enabled) : false,
  });
}

// TODO: Replace with real fetch from Agent Studio once API is available, and remove mockMcpTools from the tool connections list.
export async function getIntegrationConnections(): Promise<IntegrationConnectionView[]> {
  const liveConnections = await fetchAgentStudioIntegrationConnections();

  return clone(
    liveConnections ?? [
      {
        provider: "chatwoot",
        name: "Chatwoot",
        kind: "channel",
        status: "unconfigured",
        configured: false,
        enabled: false,
        external: true,
        base_url: null,
        account_id: null,
        inbox_id: null,
        api_mode: null,
        dry_run: true,
        writes_enabled: false,
        has_api_access_token: false,
        has_webhook_token: false,
        has_api_key: false,
        missing: ["base_url", "account_id", "api_access_token"],
        detail:
          "Chatwoot configuration is managed by Agent Studio. Set SAGAD_API_BASE_URL to load live status.",
        updated_at: null,
      },
      {
        provider: "twenty",
        name: "Twenty CRM",
        kind: "crm",
        status: "unconfigured",
        configured: false,
        enabled: false,
        external: true,
        base_url: null,
        account_id: null,
        inbox_id: null,
        api_mode: "graphql",
        dry_run: true,
        writes_enabled: false,
        has_api_access_token: false,
        has_webhook_token: false,
        has_api_key: false,
        missing: ["base_url", "api_key"],
        detail:
          "Twenty CRM is external. Store credentials in Agent Studio before enabling reads.",
        updated_at: null,
      },
    ],
  );
}

export type {
  Agent,
  ContactDriver,
  Conversation,
  DashboardData,
  McpTool,
  SopReference,
  SupervisorPod,
} from "@/lib/domain";
