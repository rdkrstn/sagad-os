import { getAgents } from "@/lib/api/sagad-api";
import { AgentsConsole } from "@/components/agent-studio/agent-studio-console";

export default async function AgentsPage() {
  const agents = await getAgents();

  return <AgentsConsole agents={agents} />;
}
