import { AiOpsReports } from "@/components/reports/ai-ops-reports";
import { getDashboardData } from "@/lib/api";

// TODO(product-nav): Decide whether this legacy route should redirect to /analytics or stay as a compatibility alias.
export default async function ReportsPage() {
  const data = await getDashboardData();

  return <AiOpsReports data={data} />;
}
