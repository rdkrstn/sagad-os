import { getSopReferences } from "@/lib/api/sagad-api";
import { QaReview } from "@/components/qa/qa-review";

export default async function QaPage() {
  const references = await getSopReferences();

  return <QaReview references={references} />;
}
