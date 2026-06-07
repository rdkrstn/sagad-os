import { getSopReferences } from "@/lib/api/sagad-api";
import { QaReview } from "@/components/qa/qa-review";

// TODO(product-nav): Decide whether this legacy QA route remains an advanced admin surface outside the product nav.
export default async function QaPage() {
  const references = await getSopReferences();

  return <QaReview references={references} />;
}
