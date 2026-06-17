import fs from "fs";
import path from "path";

// Load root .env from repository root if it exists
try {
  // Try __dirname first, fallback to process.cwd()
  let envPath = path.resolve(__dirname, "../.env");
  if (!fs.existsSync(envPath)) {
    envPath = path.resolve(process.cwd(), "../.env");
  }
  if (fs.existsSync(envPath)) {
    const envConfig = fs.readFileSync(envPath, "utf-8");
    envConfig.split(/\r?\n/).forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) return;
      const match = trimmed.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
      if (match) {
        const key = match[1];
        let val = match[2] || "";
        if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
          val = val.slice(1, -1);
        }
        if (!process.env[key]) {
          process.env[key] = val;
        }
      }
    });
  }
} catch (e) {
  console.warn("Failed to load root .env file in auth.ts:", e);
}

import PostgresAdapter from "@auth/pg-adapter";
import NextAuth, { type DefaultSession, type NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";
import Nodemailer from "next-auth/providers/nodemailer";
import type { Provider } from "next-auth/providers";
import { Pool } from "pg";

type SagadRole = "owner" | "admin" | "supervisor" | "agent" | "qa" | "viewer";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      organizationId: string | null;
      role: SagadRole | null;
    } & DefaultSession["user"];
  }
}

type AuthEnvironmentName =
  | "AUTH_SECRET"
  | "AUTH_URL"
  | "DATABASE_URL"
  | "EMAIL_FROM"
  | "EMAIL_SERVER";

type OptionalAuthEnvironmentName = "AUTH_GOOGLE_ID" | "AUTH_GOOGLE_SECRET";

const localAuthDefaults: Record<AuthEnvironmentName, string> = {
  AUTH_SECRET: "change-me-for-local-dev",
  AUTH_URL: "http://localhost:3000",
  DATABASE_URL: "postgresql://sagad:sagad_dev_password@127.0.0.1:5433/sagad_os",
  EMAIL_FROM: "Sagad OS <noreply@sagad.local>",
  EMAIL_SERVER: "smtp://localhost:1025",
};

let authPool: Pool | null = null;

function readAuthEnvironment(name: AuthEnvironmentName): string {
  return process.env[name] ?? localAuthDefaults[name];
}

function readOptionalAuthEnvironment(
  name: OptionalAuthEnvironmentName,
): string | undefined {
  const value = process.env[name]?.trim();
  return value ? value : undefined;
}

function getAuthPool(): Pool {
  if (!authPool) {
    authPool = new Pool({
      connectionString: readAuthEnvironment("DATABASE_URL"),
    });
  }

  return authPool;
}

function numericUserId(userId: string | number | undefined): number | null {
  const value = Number(userId);
  return Number.isInteger(value) ? value : null;
}

async function ensureDefaultMembership(
  userId: string | number | undefined,
  displayName: string | null | undefined,
): Promise<void> {
  const id = numericUserId(userId);
  if (id === null) {
    return;
  }

  await getAuthPool().query(
    `
    WITH default_org AS (
      SELECT id
      FROM organizations
      WHERE slug = 'johnred-workspace'
      LIMIT 1
    )
    INSERT INTO profiles (user_id, display_name, default_organization_id)
    SELECT $1, $2, default_org.id
    FROM default_org
    ON CONFLICT (user_id) DO UPDATE SET
      display_name = COALESCE(EXCLUDED.display_name, profiles.display_name),
      default_organization_id = EXCLUDED.default_organization_id,
      updated_at = now()
    `,
    [id, displayName ?? null],
  );

  await getAuthPool().query(
    `
    WITH default_org AS (
      SELECT id
      FROM organizations
      WHERE slug = 'johnred-workspace'
      LIMIT 1
    )
    INSERT INTO organization_members (organization_id, user_id, role, status)
    SELECT default_org.id, $1, 'supervisor', 'active'
    FROM default_org
    ON CONFLICT (organization_id, user_id) DO NOTHING
    `,
    [id],
  );
}

async function getDefaultMembership(
  userId: string | number | undefined,
): Promise<{ organizationId: string | null; role: SagadRole | null }> {
  const id = numericUserId(userId);
  if (id === null) {
    return { organizationId: null, role: null };
  }

  const result = await getAuthPool().query<{
    organization_id: string;
    role: SagadRole;
  }>(
    `
    SELECT organization_members.organization_id::text, organization_members.role
    FROM organization_members
    JOIN profiles ON profiles.user_id = organization_members.user_id
    WHERE organization_members.user_id = $1
      AND organization_members.status = 'active'
    ORDER BY
      CASE
        WHEN profiles.default_organization_id = organization_members.organization_id THEN 0
        ELSE 1
      END,
      organization_members.created_at ASC
    LIMIT 1
    `,
    [id],
  );

  const row = result.rows[0];
  return row
    ? { organizationId: row.organization_id, role: row.role }
    : { organizationId: null, role: null };
}

function createProviders(): Provider[] {
  const providers: Provider[] = [
    Nodemailer({
      server: readAuthEnvironment("EMAIL_SERVER"),
      from: readAuthEnvironment("EMAIL_FROM"),
    }),
  ];

  const googleClientId = readOptionalAuthEnvironment("AUTH_GOOGLE_ID");
  const googleClientSecret = readOptionalAuthEnvironment("AUTH_GOOGLE_SECRET");

  if (googleClientId && googleClientSecret) {
    providers.push(
      Google({
        clientId: googleClientId,
        clientSecret: googleClientSecret,
      }),
    );
  }

  return providers;
}

function createAuthConfig(): NextAuthConfig {
  const authUrl = readAuthEnvironment("AUTH_URL");

  return {
    adapter: PostgresAdapter(getAuthPool()),
    providers: createProviders(),
    secret: readAuthEnvironment("AUTH_SECRET"),
    session: {
      strategy: "database",
    },
    trustHost: Boolean(authUrl),
    callbacks: {
      async session({ session, user }) {
        await ensureDefaultMembership(user.id, session.user?.name);
        const membership = await getDefaultMembership(user.id);

        return {
          ...session,
          user: {
            ...session.user,
            id: String(user.id),
            organizationId: membership.organizationId,
            role: membership.role,
          },
        };
      },
    },
    events: {
      async createUser({ user }) {
        await ensureDefaultMembership(user.id, user.name);
      },
    },
  };
}

export const {
  handlers,
  auth,
  signIn,
  signOut,
} = NextAuth(createAuthConfig);
