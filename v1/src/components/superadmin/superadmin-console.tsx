import { Boxes, Building2, CheckCircle2, Database, Server, ShieldCheck, Users } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { MetricStrip } from "@/components/ui/metric-strip";
import { SectionPanel } from "@/components/ui/section-panel";
import { AdaptersConsole } from "@/components/superadmin/adapters-console";
import { MembersConsole } from "@/components/superadmin/members-console";
import { ModelProvidersPanel, type ModelProvidersView } from "@/components/superadmin/model-providers-panel";
import { SecretsPolicyPanel } from "@/components/superadmin/secrets-policy-panel";
import type { IntegrationConnectionView } from "@/lib/api";
import type { MemberView } from "@/lib/admin/members";

const ROLE_BOUNDARIES = [
  {
    icon: ShieldCheck,
    title: "Owner / Admin",
    detail: "Can configure provider credentials, model gateway settings, and write policies.",
  },
  {
    icon: CheckCircle2,
    title: "Supervisor / QA",
    detail: "Can review exceptions, inspect evidence, approve drafts, and view redacted health.",
  },
  {
    icon: Server,
    title: "Integrator",
    detail: "Can inspect adapter contracts under Settings Advanced without seeing raw secrets.",
  },
];

const PERSISTENCE_BOUNDARIES = [
  {
    icon: Database,
    title: "Sagad Postgres",
    detail:
      "Owns auth sessions, conversations, approvals, audit rows, integration config, and pgvector retrieval state.",
  },
  {
    icon: Server,
    title: "Agent Studio",
    detail: "Owns provider credentials, health checks, retries, write gates, and runtime traces.",
  },
  {
    icon: ShieldCheck,
    title: "Console",
    detail: "Owns human review workflows and only receives redacted status or approved actions.",
  },
];

export function SuperAdminConsole({
  connections,
  members,
  currentUserId,
  providers,
}: {
  connections: IntegrationConnectionView[];
  members: MemberView[];
  currentUserId: string | null;
  providers: ModelProvidersView;
}) {
  const connectedAdapters = connections.filter((row) => row.configured && row.enabled).length;

  return (
    <div>
      <PageHeader
        description="Instance-level control plane for self-hosted Sagad OS: adapter connections, members and roles, model gateway, and secrets policy."
        meta="SuperAdmin"
        title="SuperAdmin Console"
      />

      <div className="space-y-4">
        <MetricStrip
          items={[
            { label: "Workspaces", value: 1, detail: "Default workspace", icon: Building2 },
            { label: "Members", value: members.length, detail: "Owner / admin managed", icon: Users },
            {
              label: "Adapters",
              value: connections.length,
              detail: `${connectedAdapters} connected`,
              icon: Boxes,
            },
            { label: "Runtime health", value: "Live", detail: "Liveness vs readiness split", icon: CheckCircle2 },
          ]}
        />

        <SectionPanel action={null} eyebrow="Platform" title="Adapters">
          <AdaptersConsole connections={connections} />
        </SectionPanel>

        <SectionPanel action={null} eyebrow="Access" title="Members & Roles">
          <MembersConsole currentUserId={currentUserId} initialMembers={members} />
        </SectionPanel>

        <div className="grid gap-4 xl:grid-cols-2">
          <SectionPanel action={null} eyebrow="Observe" title="Model Providers">
            <ModelProvidersPanel initial={providers} />
          </SectionPanel>
          <SectionPanel action={null} eyebrow="Platform" title="Secrets Policy">
            <SecretsPolicyPanel connections={connections} />
          </SectionPanel>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <SectionPanel eyebrow="Access" title="Roles And Boundaries">
            <div className="space-y-3 p-4 text-sm">
              {ROLE_BOUNDARIES.map((role) => {
                const Icon = role.icon;
                return (
                  <div className="rounded-md border border-border bg-surface-2 p-3" key={role.title}>
                    <div className="flex items-center gap-2 font-medium">
                      <Icon aria-hidden="true" className="text-[var(--accent-text)]" size={15} />
                      {role.title}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{role.detail}</p>
                  </div>
                );
              })}
            </div>
          </SectionPanel>

          <SectionPanel eyebrow="Data" title="Persistence Boundary">
            <div className="grid gap-3 p-4 md:grid-cols-1">
              {PERSISTENCE_BOUNDARIES.map((boundary) => {
                const Icon = boundary.icon;
                return (
                  <div className="rounded-md border border-border bg-surface-2 p-3" key={boundary.title}>
                    <Icon aria-hidden="true" className="mb-2 text-[var(--accent-text)]" size={17} />
                    <div className="text-sm font-medium">{boundary.title}</div>
                    <p className="mt-1 text-xs text-muted-foreground">{boundary.detail}</p>
                  </div>
                );
              })}
            </div>
          </SectionPanel>
        </div>
      </div>
    </div>
  );
}
