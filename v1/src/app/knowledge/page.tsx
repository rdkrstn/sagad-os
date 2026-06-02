import { getSopReferences } from "@/lib/api/sagad-api";
import { KnowledgeInventory } from "@/components/knowledge/knowledge-inventory";

export default async function KnowledgePage() {
  const references = await getSopReferences();

  return <KnowledgeInventory references={references} />;
}
