import { IntegrationsHealthConsole } from "@/components/integrations/integrations-health-console";
import { getIntegrationConnections } from "@/lib/api/sagad-api";

export default async function IntegrationsPage() {
  const connections = await getIntegrationConnections();

  return <IntegrationsHealthConsole connections={connections} />;
}
