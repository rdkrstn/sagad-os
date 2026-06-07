import { GraphsConsole } from "@/components/agent-studio/agent-studio-console";
import { getGraphs } from "@/lib/api/sagad-api";

export default async function GraphsPage() {
  const graphs = await getGraphs();

  return <GraphsConsole graphs={graphs} />;
}
