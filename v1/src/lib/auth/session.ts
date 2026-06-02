import type { Session } from "next-auth";
import { auth } from "../../../auth";

export type CurrentUser = NonNullable<Session["user"]>;
export type AuthenticatedSession = Session & {
  user: CurrentUser;
};

export class AuthSessionRequiredError extends Error {
  constructor() {
    super("A signed-in Sagad OS user session is required.");
    this.name = "AuthSessionRequiredError";
  }
}

function hasCurrentUser(session: Session | null): session is AuthenticatedSession {
  return Boolean(session?.user);
}

export async function getCurrentSession(): Promise<Session | null> {
  return auth();
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const session = await getCurrentSession();

  return session?.user ?? null;
}

export async function requireCurrentSession(): Promise<AuthenticatedSession> {
  const session = await getCurrentSession();

  if (!hasCurrentUser(session)) {
    throw new AuthSessionRequiredError();
  }

  return session;
}
