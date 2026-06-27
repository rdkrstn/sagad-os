import { getAuthPool } from "@/lib/auth/db";
import { getCurrentSession } from "@/lib/auth/session";
import {
  hasIntegrationAdminRole,
  jsonResponse,
} from "@/lib/agent-studio-proxy";
import type { MemberView } from "@/lib/admin/members";

export async function GET(): Promise<Response> {
  const session = await getCurrentSession();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }
  if (!hasIntegrationAdminRole(session.user.role)) {
    return jsonResponse({ detail: "Owner or admin role required." }, 403);
  }
  const organizationId = session.user.organizationId;
  if (!organizationId) {
    return jsonResponse({ members: [] }, 200);
  }

  const result = await getAuthPool().query<MemberView>(
    `
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
    `,
    [organizationId],
  );

  return jsonResponse({ members: result.rows }, 200);
}
