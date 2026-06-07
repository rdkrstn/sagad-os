import { AnalyticsConsole } from "@/components/analytics/analytics-console";
import { getDashboardData } from "@/lib/api/sagad-api";

export default async function AnalyticsPage() {
  const data = await getDashboardData();

  return <AnalyticsConsole data={data} />;
}
