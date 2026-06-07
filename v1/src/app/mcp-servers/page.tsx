import { McpServersConsole } from "@/components/agent-studio/agent-studio-console";
import { getMcpServers } from "@/lib/api/sagad-api";

export default async function McpServersPage() {
  const servers = await getMcpServers();

  return <McpServersConsole servers={servers} />;
}
