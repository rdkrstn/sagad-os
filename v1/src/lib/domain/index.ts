export type ISODateTime = string;
export type CurrencyCode = "USD" | "PHP";

export type ConversationChannel =
  | "web_chat"
  | "sms"
  | "email"
  | "voice"
  | "facebook"
  | "instagram"
  | "whatsapp"
  | "telegram"
  | "line"
  | "api"
  | "unknown";

export type ConversationStatus =
  | "active"
  | "waiting_on_customer"
  | "waiting_on_agent"
  | "needs_review"
  | "human_takeover"
  | "resolved";

export type ConversationPriority = "low" | "normal" | "high" | "urgent";

export type MessageSenderType = "customer" | "ai_agent" | "human_agent" | "system";

export type MessageDeliveryStatus = "queued" | "sent" | "delivered" | "failed";
// TODO: Add more specific delivery status values as needed, such as "read" or "received".
export type ClassifierIntent =
  | "pricing_lead"
  | "account_support"
  | "general_support"
  | "crm_tool_failure"
  | "refund_or_cancellation"
  | "unknown";

export type ClassifierSentiment = "positive" | "neutral" | "confused" | "frustrated";

export type LeadStage =
  | "new"
  | "qualified"
  | "estimate_scheduled"
  | "booked"
  | "active_customer"
  | "at_risk"
  | "lost";

export type AgentStatus = "available" | "busy" | "reviewing" | "offline";

export type ReviewDecisionStatus =
  | "pending"
  | "approved"
  | "edited"
  | "rejected"
  | "escalated";
// TODO: Fetch from Agent Studio when API is available, and remove from the review decision status list.
export type McpToolName =
  | "chatwoot.webhook.receive"
  | "chatwoot.messages.send_approved"
  | "knowledge.retrieve_context"
  | "webhook.outbound.trigger"
  | "observability.langsmith.trace"
  | "mcp.tool_layer.dispatch"
  | "crm.lookup_contact"
  | "crm.create_note"
  | "crm.create_task"
  | "crm.schedule_appointment"
  | "crm.update_lead_stage"
  | "crm.list_service_history";

export type McpToolStatus = "available" | "degraded" | "disabled";

export type QaRating = "pass" | "watch" | "fail";

export type InterruptStatus = "none" | "pending_approval" | "resumed" | "failed";

export type ResumeAction =
  | "approve"
  | "edit_and_send"
  | "reject"
  | "assign_human"
  | "retry_tool"
  | "none";
// TODO: Add more specific resume actions as needed, such as "escalate_to_supervisor" or "request_more_info".
export type AuditTrailEventType =
  | "message_received"
  | "intent_classified"
  | "agent_selected"
  | "knowledge_retrieved"
  | "draft_generated"
  | "confidence_scored"
  | "approval_required"
  | "supervisor_action"
  | "final_response_sent";

export interface MoneyAmount {
  amount: number;
  currency: CurrencyCode;
}

export interface Message {
  id: string;
  conversationId: string;
  senderType: MessageSenderType;
  senderName: string;
  body: string;
  createdAt: ISODateTime;
  deliveryStatus: MessageDeliveryStatus;
  toolCallId?: string;
}

export interface ClassifierResult {
  intent: ClassifierIntent;
  confidence: number;
  sentiment: ClassifierSentiment;
  language: "en" | "fil" | "mixed";
  summary: string;
  urgencyScore: number;
}

export interface ContactDriver {
  id: string;
  label: string;
  description: string;
  queueCount: number;
  slaRiskCount: number;
  priority: ConversationPriority;
}

export interface Agent {
  id: string;
  name: string;
  role: "ai_agent" | "human_agent" | "supervisor";
  status: AgentStatus;
  activeConversationCount: number;
  languages: Array<"en" | "fil">;
  podId?: string;
}

export interface SupervisorPod {
  id: string;
  name: string;
  queueLabel: string;
  leadSupervisorId: string;
  agentIds: string[];
  openConversationCount: number;
  slaRiskCount: number;
}

export interface ReviewDecision {
  id: string;
  conversationId: string;
  requestedByAgentId: string;
  status: ReviewDecisionStatus;
  requestedAt: ISODateTime;
  decidedAt?: ISODateTime;
  decisionByAgentId?: string;
  proposedMessage: string;
  finalMessage?: string;
  reason: string;
}

export interface CrmTask {
  id: string;
  title: string;
  dueAt: ISODateTime;
  status: "open" | "done" | "cancelled";
  ownerId?: string;
}

export interface CrmAppointment {
  id: string;
  serviceType: string;
  scheduledFor: ISODateTime;
  status: "requested" | "confirmed" | "completed" | "cancelled";
  assignedTech?: string;
}

export interface ServiceHistoryItem {
  id: string;
  serviceType: string;
  completedAt: ISODateTime;
  technician: string;
  invoiceTotal: MoneyAmount;
  notes: string;
}

export interface CrmContact {
  id: string;
  displayName: string;
  phoneMasked: string;
  emailMasked?: string;
  city: string;
  leadStage: LeadStage;
  tags: string[];
  notes: string[];
  tasks: CrmTask[];
  appointments: CrmAppointment[];
  serviceHistory: ServiceHistoryItem[];
}

export interface McpTool {
  id: string;
  name: McpToolName;
  label: string;
  description: string;
  status: McpToolStatus;
  requiresApproval: boolean;
  lastRunAt?: ISODateTime;
}

export interface QaScore {
  id: string;
  conversationId: string;
  rating: QaRating;
  score: number;
  checkedAt: ISODateTime;
  criteria: Array<{
    label: string;
    passed: boolean;
    notes: string;
  }>;
}

export interface SopReference {
  id: string;
  title: string;
  section: string;
  summary: string;
  appliesToIntents: ClassifierIntent[];
  url: string;
}

export interface LangGraphRunSummary {
  threadId: string;
  currentNode: string;
  interruptStatus: InterruptStatus;
  approvalPayload?: {
    reviewDecisionId: string;
    proposedAction: string;
    riskLevel: "low" | "medium" | "high";
  };
  resumeAction: ResumeAction;
  traceUrl: string;
  lastUpdatedAt: ISODateTime;
}

export interface AuditTrailEvent {
  id: string;
  conversationId: string;
  type: AuditTrailEventType;
  label: string;
  status: string;
  actor:
    | "chatwoot"
    | "sagad_core"
    | "sagad_agents"
    | "sagad_knowledge"
    | "sagad_approvals"
    | "sagad_audit"
    | "supervisor";
  detail: string;
  createdAt: ISODateTime;
}

export interface Conversation {
  id: string;
  contactId: string;
  assignedAgentId?: string;
  supervisorPodId: string;
  channel: ConversationChannel;
  status: ConversationStatus;
  priority: ConversationPriority;
  subject: string;
  openedAt: ISODateTime;
  updatedAt: ISODateTime;
  slaDueAt: ISODateTime;
  classifier: ClassifierResult;
  messages: Message[];
  reviewDecision?: ReviewDecision;
  qaScore?: QaScore;
  langGraphRun: LangGraphRunSummary;
  toolCallIds: string[];
  auditEvents?: AuditTrailEvent[];
}

export interface DashboardData {
  account: {
    id: string;
    name: string;
    industry: "home_services" | "internal_ops" | "retail" | "bpo";
    timezone: string;
  };
  conversations: Conversation[];
  contacts: CrmContact[];
  agents: Agent[];
  supervisorPods: SupervisorPod[];
  contactDrivers: ContactDriver[];
  sopReferences: SopReference[];
  mcpTools: McpTool[];
}
