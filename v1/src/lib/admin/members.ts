import { getAuthPool, type SagadRole } from "@/lib/auth/db";
import { getCurrentSession } from "@/lib/auth/session";
import { hasIntegrationAdminRole } from "@/lib/agent-studio-proxy";

export type MemberView = {
  user_id: string;
  name: string | null;
  email: string | null;
  role: SagadRole;
  status: "active" | "invited" | "disabled";
  created_at: string | null;
};

const ROLES: SagadRole[] = ["owner", "admin", "supervisor", "agent", "qa", "viewer"];

export function isSagadRole(value: unknown): value is SagadRole {
  return typeof value === "string" && (ROLES as string[]).includes(value);
}

const MEMBERS_QUERY = `
  SELECT
    users.id::text AS user_id,
    users.name,
    users.email,
    organization_members.role,
    organization_members.status,
    organization_members.created_at::text AS created_at
  FROM organization_members
  JOIN users ON users.id = organization_members.user_id
  WHERE organization_members.organization_id = $1
  ORDER BY users.name, users.email
`;

/** Server-side initial fetch for the SuperAdmin members section (owner/admin gated). */
export async function getOrgMembers(): Promise<MemberView[]> {
  const session = await getCurrentSession();
  if (!session?.user?.id || !hasIntegrationAdminRole(session.user.role)) {
    return [];
  }
  const organizationId = session.user.organizationId;
  if (!organizationId) {
    return [];
  }
  try {
    const result = await getAuthPool().query<MemberView>(MEMBERS_QUERY, [organizationId]);
    return result.rows;
  } catch {
    // Degrade gracefully when the DB is briefly unavailable so the SuperAdmin page still
    // renders adapters/gateway/secrets. The members API endpoints will surface real errors.
    return [];
  }
}
