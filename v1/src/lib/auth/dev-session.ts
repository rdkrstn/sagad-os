import type { Session } from "next-auth";
import { cookies } from "next/headers";

export const DEV_SESSION_COOKIE = "sagad-dev-session";
export const DEV_SESSION_VALUE = "sagad-dev-owner";

export function devSessionEnabled(): boolean {
  return process.env.NODE_ENV !== "production";
}

export async function getDevSession(): Promise<Session | null> {
  if (!devSessionEnabled()) {
    return null;
  }

  const cookieStore = await cookies();
  if (cookieStore.get(DEV_SESSION_COOKIE)?.value !== DEV_SESSION_VALUE) {
    return null;
  }

  return {
    expires: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString(),
    user: {
      id: "dev-owner",
      name: "Sagad Dev Owner",
      email: "dev@sagad.local",
      image: null,
      organizationId: "dev-johnred-workspace",
      role: "owner",
    },
  };
}
