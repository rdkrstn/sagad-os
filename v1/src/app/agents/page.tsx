import { getAgents } from "@/lib/api/sagad-api";
import { AgentPerformance } from "@/components/agents/agent-performance";

// TODO(product-nav): Decide whether this legacy analysis route remains an advanced admin surface outside the product nav.
export default async function AgentsPage() {
  const agents = await getAgents();

  return <AgentPerformance agents={agents} />;
}
