import { getAgents } from "@/lib/api/sagad-api";
import { AgentPerformance } from "@/components/agents/agent-performance";

export default async function AgentsPage() {
  const agents = await getAgents();

  return <AgentPerformance agents={agents} />;
}
