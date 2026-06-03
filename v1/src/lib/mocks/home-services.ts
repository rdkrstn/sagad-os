import type {
  Agent,
  ContactDriver,
  Conversation,
  CrmContact,
  DashboardData,
  McpTool,
  SopReference,
  SupervisorPod,
} from "@/lib/domain";

export const mockAgents: Agent[] = [];

export const mockSupervisorPods: SupervisorPod[] = [];

export const mockContactDrivers: ContactDriver[] = [];

export const mockContacts: CrmContact[] = [];

export const mockConversations: Conversation[] = [];

export const mockSopReferences: SopReference[] = [];

export const mockMcpTools: McpTool[] = [
  {
    id: "tool-crm-lookup-contact",
    name: "crm.lookup_contact",
    label: "Lookup contact",
    description: "Find a CRM contact by phone, email, or conversation metadata.",
    status: "available",
    requiresApproval: false,
  },
  {
    id: "tool-crm-create-note",
    name: "crm.create_note",
    label: "Create note",
    description: "Append a supervisor-approved CRM note to the selected contact.",
    status: "available",
    requiresApproval: true,
  },
  {
    id: "tool-crm-create-task",
    name: "crm.create_task",
    label: "Create task",
    description: "Create a follow-up task for a human operator or supervisor.",
    status: "available",
    requiresApproval: true,
  },
  {
    id: "tool-crm-update-lead-stage",
    name: "crm.update_lead_stage",
    label: "Update lead stage",
    description: "Move a contact through an external CRM pipeline after approval.",
    status: "degraded",
    requiresApproval: true,
  },
  {
    id: "tool-crm-list-service-history",
    name: "crm.list_service_history",
    label: "List service history",
    description: "Read prior completed services for a verified contact.",
    status: "available",
    requiresApproval: false,
  },
];

export const homeServicesDashboardData: DashboardData = {
  account: {
    id: "acct-johnred-demafeliz",
    name: "Johnred Demafeliz",
    industry: "internal_ops",
    timezone: "Asia/Manila",
  },
  conversations: mockConversations,
  contacts: mockContacts,
  agents: mockAgents,
  supervisorPods: mockSupervisorPods,
  contactDrivers: mockContactDrivers,
  sopReferences: mockSopReferences,
  mcpTools: mockMcpTools,
};
