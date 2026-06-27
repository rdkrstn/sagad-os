import { getAuthPool } from "@/lib/auth/db";
import { getCurrentSession } from "@/lib/auth/session";
import {
  hasIntegrationAdminRole,
  jsonResponse,
} from "@/lib/agent-studio-proxy";
import { isSagadRole } from "@/lib/admin/members";

interface RouteContext {
  params: Promise<{ id: string }>;
}

function numericUserId(value: string): number | null {
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : null;
}

async function countActiveOwners(organizationId: string): Promise<number> {
  const result = await getAuthPool().query<{ count: string }>(
    `
    SELECT COUNT(*)::text AS count
    FROM organization_members
    WHERE organization_id = $1 AND role = 'owner' AND status = 'active'
    `,
    [organizationId],
  );
  return Number(result.rows[0]?.count ?? 0);
}

async function currentMembership(organizationId: string, userId: number) {
  const result = await getAuthPool().query<{
    role: string;
    status: string;
  }>(
    `
    SELECT role, status
    FROM organization_members
    WHERE organization_id = $1 AND user_id = $2
    `,
    [organizationId, userId],
  );
  return result.rows[0] ?? null;
}

export async function PATCH(request: Request, context: RouteContext): Promise<Response> {
  const session = await getCurrentSession();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }
  if (!hasIntegrationAdminRole(session.user.role)) {
    return jsonResponse({ detail: "Owner or admin role required." }, 403);
  }
  const organizationId = session.user.organizationId;
  if (!organizationId) {
    return jsonResponse({ detail: "No active organization." }, 400);
  }

  const { id } = await context.params;
  const userId = numericUserId(id);
  if (userId === null) {
    return jsonResponse({ detail: "Invalid member id." }, 400);
  }

  const body = (await request.json().catch(() => ({}))) as {
    role?: unknown;
    status?: unknown;
  };
  const membership = await currentMembership(organizationId, userId);
  if (!membership) {
    return jsonResponse({ detail: "Member not found in this organization." }, 404);
  }

  const nextRole = body.role;
  const nextStatus = body.status;
  const demotingOwner =
    membership.role === "owner" && nextRole !== undefined && nextRole !== "owner";
  const disablingOwner =
    membership.status === "active" &&
    membership.role === "owner" &&
    nextStatus === "disabled";
  if (demotingOwner || disablingOwner) {
    const owners = await countActiveOwners(organizationId);
    if (owners <= 1) {
      return jsonResponse(
        { detail: "Cannot demote or disable the last owner of the organization." },
        409,
      );
    }
  }

  const sets: string[] = [];
  const values: unknown[] = [organizationId, userId];
  let paramIndex = 3;
  if (nextRole !== undefined) {
    if (!isSagadRole(nextRole)) {
      return jsonResponse({ detail: `Invalid role: ${String(nextRole)}.` }, 400);
    }
    sets.push(`role = $${paramIndex}`);
    values.push(nextRole);
    paramIndex += 1;
  }
  if (nextStatus !== undefined) {
    if (nextStatus !== "active" && nextStatus !== "disabled" && nextStatus !== "invited") {
      return jsonResponse({ detail: `Invalid status: ${String(nextStatus)}.` }, 400);
    }
    sets.push(`status = $${paramIndex}`);
    values.push(nextStatus);
    paramIndex += 1;
  }
  if (sets.length === 0) {
    return jsonResponse({ detail: "Nothing to update." }, 400);
  }
  sets.push("updated_at = now()");

  const result = await getAuthPool().query<{
    role: string;
    status: string;
  }>(
    `
    UPDATE organization_members
    SET ${sets.join(", ")}
    WHERE organization_id = $1 AND user_id = $2
    RETURNING role, status
    `,
    values,
  );

  const updated = result.rows[0];
  return jsonResponse(
    {
      user_id: String(userId),
      role: updated?.role ?? membership.role,
      status: updated?.status ?? membership.status,
    },
    200,
  );
}

export async function DELETE(_request: Request, context: RouteContext): Promise<Response> {
  const session = await getCurrentSession();
  if (!session?.user?.id) {
    return jsonResponse({ detail: "Authentication required." }, 401);
  }
  if (!hasIntegrationAdminRole(session.user.role)) {
    return jsonResponse({ detail: "Owner or admin role required." }, 403);
  }
  const organizationId = session.user.organizationId;
  if (!organizationId) {
    return jsonResponse({ detail: "No active organization." }, 400);
  }

  const { id } = await context.params;
  const userId = numericUserId(id);
  if (userId === null) {
    return jsonResponse({ detail: "Invalid member id." }, 400);
  }

  const membership = await currentMembership(organizationId, userId);
  if (!membership) {
    return jsonResponse({ detail: "Member not found in this organization." }, 404);
  }
  if (membership.role === "owner" && membership.status === "active") {
    const owners = await countActiveOwners(organizationId);
    if (owners <= 1) {
      return jsonResponse(
        { detail: "Cannot disable the last owner of the organization." },
        409,
      );
    }
  }

  await getAuthPool().query(
    `
    UPDATE organization_members
    SET status = 'disabled', updated_at = now()
    WHERE organization_id = $1 AND user_id = $2
    `,
    [organizationId, userId],
  );

  return jsonResponse({ user_id: String(userId), status: "disabled" }, 200);
}
