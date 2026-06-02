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

interface AgentStudioConversation {
  id: string;
  chatwoot_conversation_id: string | null;
  customer_name: string;
  channel: string;
  incoming_message: string;
  normalized_message: string;
  intent: string;
  risk_level: "low" | "medium" | "high";
  retrieved_knowledge: AgentStudioKnowledgeHit[];
  draft_reply: string;
  qa_findings: AgentStudioQaFinding[];
  compliance_status: "pass" | "needs_review" | "blocked";
  approval_status: string;
  send_status: string;
  trace_url: string | null;
  created_at: string;
  updated_at: string;
}

interface AgentStudioConversationList {
  conversations: AgentStudioConversation[];
}

const demoNow = "2026-05-31T11:48:00-07:00";
const clone = <T>(value: T): T => structuredClone(value);

const contactById = new Map(mockContacts.map((contact) => [contact.id, contact]));
const agentById = new Map(mockAgents.map((agent) => [agent.id, agent]));
const podById = new Map(mockSupervisorPods.map((pod) => [pod.id, pod]));
const toolById = new Map(mockMcpTools.map((tool) => [tool.id, tool]));

function agentStudioBaseUrl(): string | null {
  const value = process.env.SAGAD_API_BASE_URL?.trim();
  return value ? value.replace(/\/$/, "") : null;
}

async function fetchAgentStudioConversations(): Promise<AgentStudioConversation[] | null> {
  const baseUrl = agentStudioBaseUrl();
  if (!baseUrl) {
    return null;
  }

  try {
    const response = await fetch(`${baseUrl}/conversations`, {
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
  if (intent.includes("refund") || intent.includes("cancellation")) return "Retention";
  if (intent.includes("discovery") || intent.includes("unknown")) return "Discovery";
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
      step: "HITL review",
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
  if (intent === "discovery") return "discovery";
  if (intent === "refund_or_cancellation") return "refund_or_cancellation";
  if (intent === "booking_or_support" || intent === "general_support") {
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

  return {
    id: conversation.id,
    contactId: `chatwoot-${conversation.chatwoot_conversation_id ?? conversation.id}`,
    assignedAgentId: "agent-ai-dispatch",
    supervisorPodId: "pod-intake",
    channel: "web_chat",
    subject: conversation.incoming_message.slice(0, 80),
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
    toolCallIds: [],
    customerName: conversation.customer_name,
    contact: conversation.customer_name,
    name: conversation.customer_name,
    source: "Chatwoot",
    channelProvider: "Chatwoot",
    lane,
    queueType: lane,
    reason: "Agent Studio generated a draft that requires HITL approval before sending.",
    queueReason: "HITL-only Chatwoot send policy",
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
    lastMessage: conversation.incoming_message,
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
        rationale: "HITL-only preview policy requires approval before send.",
      },
    ],
    aiDecisionTrail: [],
    messages: [
      {
        id: `${conversation.id}-inbound`,
        sender: conversation.customer_name,
        role: "Customer",
        body: conversation.incoming_message,
        createdAt: conversation.created_at,
        time: new Date(conversation.created_at).toLocaleTimeString("en-US", {
          hour: "numeric",
          minute: "2-digit",
        }),
      },
    ],
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
        ? "Discovery agent should ask a probing question."
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
    hitlStatus: conversation.reviewDecision ? "Needs approval" : "Not required",
    sendStatus: "Mock",
    complianceStatus: conversation.reviewDecision ? "Needs review" : "Pass",
    knowledgeContext: [
      {
        title: "Home Services Demo Knowledge",
        category: "Mock",
        source: "src/lib/mocks/home-services.ts",
        score: 1,
        excerpt: conversation.classifier.summary,
      },
    ],
    qaCompliance: [
      {
        label: "HITL policy",
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
  const actual: AgentView[] = mockAgents.map((agent) => ({
    ...agent,
    role: titleCase(agent.role),
    lane:
      agent.role === "supervisor"
        ? "Supervisor"
        : agent.role === "human_agent"
          ? "Support"
          : "Sales / Support / Discovery",
    supervisor: "Rio Santos",
    podLead: "Rio Santos",
    owner: "Intake Pod",
    handled: agent.activeConversationCount * 12 + 14,
    resolved: agent.activeConversationCount * 8 + 9,
    volume: agent.activeConversationCount,
    aht: agent.role === "supervisor" ? "n/a" : "4m 18s",
    avgHandleTime: agent.role === "supervisor" ? "n/a" : "4m 18s",
    qaScore: agent.role === "supervisor" ? "n/a" : "92",
    qualityScore: agent.role === "supervisor" ? "n/a" : "92",
    health: titleCase(agent.status),
  }));

  return [
    ...actual,
    {
      id: "agent-sales-ai",
      name: "Sales Agent",
      role: "AI Agent",
      lane: "Sales",
      supervisor: "Rio Santos",
      podLead: "Rio Santos",
      handled: 31,
      resolved: 24,
      volume: 31,
      aht: "3m 42s",
      avgHandleTime: "3m 42s",
      qaScore: "94",
      qualityScore: "94",
      status: "Active",
      health: "Healthy",
    },
    {
      id: "agent-support-ai",
      name: "Support Agent",
      role: "AI Agent",
      lane: "Support",
      supervisor: "Rio Santos",
      podLead: "Rio Santos",
      handled: 26,
      resolved: 18,
      volume: 26,
      aht: "5m 08s",
      avgHandleTime: "5m 08s",
      qaScore: "91",
      qualityScore: "91",
      status: "Active",
      health: "Watch",
    },
    {
      id: "agent-discovery-ai",
      name: "Discovery Agent",
      role: "AI Agent",
      lane: "Discovery",
      supervisor: "Rio Santos",
      podLead: "Rio Santos",
      handled: 19,
      resolved: 14,
      volume: 19,
      aht: "2m 54s",
      avgHandleTime: "2m 54s",
      qaScore: "90",
      qualityScore: "90",
      status: "Active",
      health: "Healthy",
    },
    ...["Technical", "Retention", "Fraud/Risk"].map((lane) => ({
      id: `agent-${lane.toLowerCase().replace("/", "-")}-ai`,
      name: `${lane} Agent`,
      role: "AI Agent",
      lane,
      supervisor: "Unassigned",
      podLead: "Unassigned",
      handled: 0,
      resolved: 0,
      volume: 0,
      aht: "n/a",
      avgHandleTime: "n/a",
      qaScore: "n/a",
      qualityScore: "n/a",
      status: "Planned",
      health: "Planned",
    })),
  ];
}

function toDriverView(driver: ContactDriver): DriverView {
  const ahtByDriver: Record<string, string> = {
    "driver-pricing": "3m 42s",
    "driver-discovery": "2m 54s",
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
    "driver-pricing": {
      workstream: "Sales",
      platform: "Chatwoot",
      integration: "Twenty CRM",
      csat: "92%",
      qaScore: "94%",
      fcr: "82%",
      costInteraction: "$0.08",
    },
    "driver-discovery": {
      workstream: "Discovery",
      platform: "Chatwoot",
      integration: "Markdown KB",
      csat: "88%",
      qaScore: "90%",
      fcr: "74%",
      costInteraction: "$0.04",
    },
    "driver-account-support": {
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
    "driver-takeover": {
      workstream: "Retention",
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
    updatedAt: "May 31, 2026",
    lastUpdated: "May 31, 2026",
    status: qa.status,
    health: qa.status,
    rubric: `${reference.title} Rubric`,
    score: qa.score,
    adherence: qa.score,
    passRate: qa.score,
    flags: qa.flags,
    policyFlags: qa.flags,
    coachingNote: qa.note,
    note: qa.note,
    recommendation: qa.note,
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
            contactId: "contact-morgan-tool",
            serviceType: "Electrical inspection",
            requestedFor: "2026-06-01T10:00:00-07:00",
          }
        : {
            contactId: "contact-avery-price",
            conversationId: "conv-pricing-lead",
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
    mode: tool.requiresApproval ? "HITL gated" : "Server-side read",
    owner: tool.requiresApproval ? "Supervisor Ops" : "Ops",
    team: tool.requiresApproval ? "Supervisor Ops" : "Ops",
    health: titleCase(tool.status),
    samplePayload: JSON.stringify(samplePayload, null, 2),
    payload: JSON.stringify(samplePayload, null, 2),
  };
}

function previewToolViews(): ToolView[] {
  return [
    {
      id: "tool-chatwoot-webhook",
      name: "crm.create_note",
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
          content: "How much does an AC tune-up cost?",
          conversation: { id: 42 },
        },
        null,
        2,
      ),
    },
    {
      id: "tool-chatwoot-send-approved",
      name: "crm.create_note",
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
      health: "HITL only",
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
      name: "crm.lookup_contact",
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
          intent: "pricing_lead",
          risk_level: "low",
          query: "AC tune-up price",
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
          query: "Avery Hill",
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
      mode: "HITL gated webhook",
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
      name: "crm.create_note",
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

function queueHealth(conversations: ConversationView[]): ViewRecord[] {
  return ["Sales", "Support", "Discovery", "Retention"].map((queue) => {
    const rows = conversations.filter(
      (conversation) =>
        String(conversation.driver).includes(queue) ||
        String(conversation.lane).includes(queue) ||
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
      channel: "HITL Send",
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
      owner: "Intake Pod",
      team: "Intake Pod",
      pod: "Intake Pod",
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

export async function getDashboardData(): Promise<DashboardViewData> {
  const liveConversations = await fetchAgentStudioConversations();
  const source = liveConversations ? "agent-studio" : "mock";
  const conversations =
    liveConversations?.map(toAgentStudioConversationView) ??
    mockConversations.map(toConversationView);

  return clone({
    ...homeServicesDashboardData,
    conversations,
    agents: toAgentViews(),
    supervisorPods: supervisorPodViews(),
    contactDrivers: mockContactDrivers.map(toDriverView),
    sopReferences: mockSopReferences.map(toSopView),
    mcpTools: mockMcpTools.map(toToolView),
    accountName: homeServicesDashboardData.account.name,
    lastUpdated: "May 31, 2026 11:48 AM",
    asOf: "May 31, 2026 11:48 AM",
    metrics: {
      openQueue: conversations.length,
      openItems: conversations.length,
      queueCount: conversations.length,
      slaRisk: conversations.filter((conversation) => conversation.priority === "High risk")
        .length,
      slaBreaches: conversations.filter(
        (conversation) => conversation.priority === "High risk",
      ).length,
      atRisk: conversations.filter((conversation) => conversation.priority === "High risk")
        .length,
      approvalLoad: conversations.filter((conversation) =>
        ["Approval", "Escalated", "Failed tool/send"].includes(String(conversation.lane)),
      ).length,
      pendingApprovals: conversations.filter((conversation) =>
        ["Approval", "Escalated", "Failed tool/send"].includes(String(conversation.lane)),
      ).length,
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

  return clone(toConversationView(primaryConversation));
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

export async function getSopRefs(): Promise<SopView[]> {
  return getSopReferences();
}

export async function getMcpTools(): Promise<ToolView[]> {
  return clone([...previewToolViews(), ...mockMcpTools.map(toToolView)]);
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
