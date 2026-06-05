import type {
  ClassifierIntent,
  ContactDriver,
  Conversation,
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
import { auth } from "../../../auth";

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
  retrieved_knowledge: AgentStudioKnowledgeHit[];
  tool_plans: AgentStudioToolPlan[];
  tool_results: AgentStudioToolResult[];
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
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface AgentStudioKnowledgeDocumentList {
  documents: AgentStudioKnowledgeDocument[];
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

interface AgentStudioKnowledgeIngestionJobList {
  jobs: AgentStudioKnowledgeIngestionJob[];
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

const demoNow = "2026-06-04T09:00:00+08:00";
const clone = <T>(value: T): T => structuredClone(value);

const contactById = new Map(mockContacts.map((contact) => [contact.id, contact]));
const agentById = new Map(mockAgents.map((agent) => [agent.id, agent]));
const podById = new Map(mockSupervisorPods.map((pod) => [pod.id, pod]));
const toolById = new Map(mockMcpTools.map((tool) => [tool.id, tool]));

function agentStudioBaseUrl(): string | null {
  const value = process.env.SAGAD_API_BASE_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

async function agentStudioHeaders(): Promise<HeadersInit> {
  const headers = new Headers();
  const secret = process.env.AGENT_STUDIO_INTERNAL_SECRET?.trim();
  if (secret) {
    headers.set("X-Sagad-Internal-Secret", secret);
  }

  const session = await auth();
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

async function fetchAgentStudioKnowledgeDocuments(): Promise<AgentStudioKnowledgeDocument[] | null> {
  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return null;
  }

  try {
    const response = await fetch(`${baseUrl}/knowledge/documents`, {
      headers: await agentStudioHeaders(),
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as AgentStudioKnowledgeDocumentList;
    return Array.isArray(payload.documents) ? payload.documents : null;
  } catch {
    return null;
  }
}

async function fetchAgentStudioKnowledgeJobs(): Promise<AgentStudioKnowledgeIngestionJob[] | null> {
  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return null;
  }

  try {
    const response = await fetch(`${baseUrl}/knowledge/ingestion-jobs`, {
      headers: await agentStudioHeaders(),
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as AgentStudioKnowledgeIngestionJobList;
    return Array.isArray(payload.jobs) ? payload.jobs : null;
  } catch {
    return null;
  }
}

function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
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

function classifierIntentForAgentStudio(intent: string): ClassifierIntent {
  if (intent === "pricing_lead") return "pricing_lead";
  if (intent === "general_support") return "general_support";
  if (intent === "refund_or_cancellation") return "refund_or_cancellation";
  if (intent === "booking_or_support") {
    return "account_support";
  }
  return "unknown";
}

function toAgentStudioConversationView(
  conversation: AgentStudioConversation,
): ConversationView {
  const lane = laneForAgentStudioConversation(conversation);
  const confidence = conversation.retrieved_knowledge.length > 0 ? 0.88 : 0.68;
  const ageMinutes = minutesBetween(conversation.created_at, new Date().toISOString());
  const knowledgeContext = conversation.retrieved_knowledge.map((hit) => ({
    title: hit.title,
    category: titleCase(hit.category),
    source: hit.source_path,
    score: hit.score,
    excerpt: hit.excerpt,
  }));
  const qaCompliance = conversation.qa_findings.map((finding) => ({
    label: finding.label,
    status: titleCase(finding.status),
    detail: finding.detail,
  }));
  const toolResults = (conversation.tool_results ?? []).map((result) => ({
    id: result.id,
    planId: result.plan_id,
    provider: result.provider,
    toolName: result.tool_name,
    status: titleCase(result.status),
    detail: result.detail,
    externalId: result.external_id,
    data: result.data,
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
  }));
  const toolPlans = (conversation.tool_plans ?? []).map((plan) => ({
    id: plan.id,
    provider: plan.provider,
    toolName: plan.tool_name,
    action: plan.action,
    riskLevel: titleCase(plan.risk_level),
    requiresApproval: plan.requires_approval,
    approved: plan.approved,
    dryRun: plan.dry_run,
    args: plan.args,
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
    channel: "web_chat",
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
    deliveryResults: toolResults,
    customerName: conversation.customer_name,
    contact: conversation.customer_name,
    name: conversation.customer_name,
    source: "Chatwoot",
    channelProvider: "Chatwoot",
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
    qaCompliance,
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
      area: "Web chat",
    },
    customerContext: {
      lifecycle: "Chatwoot visitor",
      lastJob: "n/a",
      customerValue: "Unknown",
      risk: titleCase(conversation.risk_level),
      owner: "Intake Pod",
      area: "Web chat",
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
      ...toolResults.map((result) => ({
        step: result.toolName,
        status: result.status,
        rationale: result.detail,
      })),
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
    qaCompliance: [
      {
        label: "Supervisor approval policy",
        status: conversation.reviewDecision ? "Watch" : "Pass",
        detail: conversation.reviewDecision?.reason ?? "No supervisor approval required in mock state.",
      },
    ],
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
      owner: "Northstar AI Ops Pod",
      team: "Northstar AI Ops Pod",
      pod: "Northstar AI Ops Pod",
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
        String(conversation.sendStatus).toLowerCase().includes("sent"),
      ).length,
      autoSent: isDemoSeed ? 42 : conversations.filter((conversation) =>
        String(conversation.sendStatus).toLowerCase().includes("sent"),
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

export async function getKnowledgeIngestionOverview(): Promise<ViewRecord> {
  const [liveDocuments, liveJobs] = await Promise.all([
    fetchAgentStudioKnowledgeDocuments(),
    fetchAgentStudioKnowledgeJobs(),
  ]);
  const documents =
    liveDocuments?.map((document) => ({
      id: document.id,
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
      updatedAt: document.updated_at,
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
      errors: job.errors,
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

  const sources = [
    {
      name: "Manual Uploads",
      type: "Files",
      status: "Ready",
      sync: "Manual",
      detail: "MD, TXT, PDF, DOCX, XLSX, CSV, and transcripts through Agent Studio.",
    },
    {
      name: "Markdown Knowledge Packs",
      type: "Local source",
      status: "Ready",
      sync: "Manual re-index",
      detail: "Seed KB, SOP, QA, compliance, escalation, and template records.",
    },
    {
      name: "Google Drive",
      type: "Cloud source",
      status: "Planned",
      sync: "24h planned",
      detail: "Future source adapter behind Agent Studio; not browser-direct.",
    },
    {
      name: "Websites",
      type: "Public URLs",
      status: "Planned",
      sync: "Weekly planned",
      detail: "Future public source adapter with manual refresh.",
    },
  ];

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
    source: liveDocuments || liveJobs ? "agent-studio" : "mock",
  });
}

export async function getSopRefs(): Promise<SopView[]> {
  return getSopReferences();
}

export async function getMcpTools(): Promise<ToolView[]> {
  return clone([...previewToolViews(), ...mockMcpTools.map(toToolView)]);
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
