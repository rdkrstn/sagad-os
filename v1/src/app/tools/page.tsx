import { ToolsConsole } from "@/components/agent-studio/agent-studio-console";
import { getMcpTools } from "@/lib/api/sagad-api";

export default async function ToolsPage() {
  const tools = await getMcpTools();

  return <ToolsConsole tools={tools} />;
}
