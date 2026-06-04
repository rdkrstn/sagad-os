import { AiOpsReports } from "@/components/reports/ai-ops-reports";
import { getDashboardData } from "@/lib/api";

export default async function ReportsPage() {
  const data = await getDashboardData();

  return <AiOpsReports data={data} />;
}

