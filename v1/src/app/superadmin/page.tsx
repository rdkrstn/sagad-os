import { SuperAdminConsole } from "@/components/superadmin/superadmin-console";
import { getIntegrationConnections, getModelProviders } from "@/lib/api/sagad-api";
import { getOrgMembers } from "@/lib/admin/members";
import { getCurrentUser } from "@/lib/auth/session";

export default async function SuperAdminPage() {
  const [connections, members, currentUser, providers] = await Promise.all([
    getIntegrationConnections(),
    getOrgMembers(),
    getCurrentUser(),
    getModelProviders(),
  ]);

  return (
    <SuperAdminConsole
      connections={connections}
      currentUserId={currentUser?.id ?? null}
      members={members}
      providers={providers}
    />
  );
}
