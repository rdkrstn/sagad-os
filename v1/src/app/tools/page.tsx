import { auth } from "../../../auth";
import { ToolCatalog } from "@/components/tools/tool-catalog";
import { getIntegrationConnections } from "@/lib/api/sagad-api";

// TODO(product-nav): Decide whether this legacy admin-heavy route should redirect to /integrations or move behind an advanced surface.
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
