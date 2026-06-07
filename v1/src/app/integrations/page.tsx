import { IntegrationsHealthConsole } from "@/components/integrations/integrations-health-console";
import { getIntegrationHealth } from "@/lib/api/sagad-api";

export default async function IntegrationsPage() {
  const connections = await getIntegrationHealth();

  return <IntegrationsHealthConsole connections={connections} />;
}
