import { getMcpTools } from "@/lib/api/sagad-api";
import { ToolCatalog } from "@/components/tools/tool-catalog";

export default async function ToolsPage() {
  const tools = await getMcpTools();

  return <ToolCatalog tools={tools} />;
}
