import type { Session } from "next-auth";
import {
  getCurrentSession,
  getCurrentUser,
  requireCurrentSession,
} from "./session";
import { auth, signIn, signOut } from "../../../auth";

async function readServerSession() {
  return auth();
}

type AwaitedSession = Awaited<ReturnType<typeof readServerSession>>;
type HelperSession = Awaited<ReturnType<typeof getCurrentSession>>;
type RequiredSession = Awaited<ReturnType<typeof requireCurrentSession>>;
type CurrentUser = Awaited<ReturnType<typeof getCurrentUser>>;

const session: Session | null = null as AwaitedSession;
const helperSession: Session | null = null as HelperSession;
const requiredSession: Session = {} as RequiredSession;
const currentUser: Session["user"] | null = null as CurrentUser;

void session;
void helperSession;
void requiredSession;
void currentUser;
void readServerSession;
void signIn;
void signOut;
