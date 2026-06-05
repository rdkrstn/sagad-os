import { getKnowledgeIngestionOverview } from "@/lib/api/sagad-api";
import { KnowledgeInventory } from "@/components/knowledge/knowledge-inventory";

export default async function KnowledgePage() {
  const overview = await getKnowledgeIngestionOverview();

  return <KnowledgeInventory overview={overview} />;
}
