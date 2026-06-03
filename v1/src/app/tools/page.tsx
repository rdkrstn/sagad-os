import { auth } from "../../../auth";
import { ToolCatalog } from "@/components/tools/tool-catalog";
import { getIntegrationConnections } from "@/lib/api/sagad-api";

export default async function ToolsPage() {
  const session = await auth();
  const currentRole = session?.user?.role ?? "viewer";
  const canManage = currentRole === "owner" || currentRole === "admin";
  const connections = await getIntegrationConnections();

  return (
    <ToolCatalog
      canManage={canManage}
      connections={connections}
      currentRole={currentRole}
    />
  );
}
