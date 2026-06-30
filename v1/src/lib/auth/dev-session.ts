import type { Session } from "next-auth";
import { cookies } from "next/headers";
import { getAuthPool } from "@/lib/auth/db";

export const DEV_SESSION_COOKIE = "sagad-dev-session";
export const DEV_SESSION_VALUE = "sagad-dev-owner";

export function devSessionEnabled(): boolean {
  return process.env.NODE_ENV !== "production";
}

// The dev session must point at the REAL default organization + owner row, not a fake
// slug-like string. `organizations.id` is UUID and `users.id` is INTEGER, and every org-scoped
// admin query (members, integration-configs, model-providers, conversations) casts the session
// organizationId / userId to those column types. A fake `organizationId: "dev-johnred-workspace"`
// made Postgres raise `invalid input syntax for type uuid` and 500'd every org-scoped route —
// including the console's organization/members view. Resolve the real ids once (cached) from the
// auth DB by slug; fall back to null org (graceful empty) only when the DB is unreachable, and do
// NOT cache that so the next request retries once the DB is ready.
type DevOwnerContext = { userId: string; organizationId: string };

let _resolved: DevOwnerContext | null | undefined; // undefined = not yet attempted

async function resolveDevOwnerContext(): Promise<DevOwnerContext | null> {
  if (_resolved !== undefined) {
    return _resolved;
  }
  try {
    const result = await getAuthPool().query<{
      user_id: string;
      organization_id: string;
    }>(
      `
      SELECT u.id::text AS user_id, o.id::text AS organization_id
      FROM organizations o
      JOIN organization_members om ON om.organization_id = o.id
      JOIN users u ON u.id = om.user_id
      WHERE o.slug = 'johnred-workspace'
        AND u.email = 'owner@sagad.local'
        AND om.role = 'owner'
        AND om.status = 'active'
      LIMIT 1
      `,
    );
    const row = result.rows[0];
    if (row) {
      _resolved = { userId: row.user_id, organizationId: row.organization_id };
      return _resolved;
    }
    return null; // org/owner not seeded yet; do not cache so the next request retries
  } catch {
    return null; // DB unreachable; do not cache
  }
}

export async function getDevSession(): Promise<Session | null> {
  if (!devSessionEnabled()) {
    return null;
  }

  const cookieStore = await cookies();
  if (cookieStore.get(DEV_SESSION_COOKIE)?.value !== DEV_SESSION_VALUE) {
    return null;
  }

  const ctx = await resolveDevOwnerContext();
  return {
    expires: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString(),
    user: {
      id: ctx?.userId ?? "dev-owner",
      name: "Sagad Dev Owner",
      email: "dev@sagad.local",
      image: null,
      organizationId: ctx?.organizationId ?? null,
      role: "owner",
    },
  };
}