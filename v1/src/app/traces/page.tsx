import { TracesConsole } from "@/components/agent-studio/agent-studio-console";
import { getAgentRunTraces } from "@/lib/api/sagad-api";

export default async function TracesPage() {
  const traces = await getAgentRunTraces();

  return <TracesConsole traces={traces} />;
}
