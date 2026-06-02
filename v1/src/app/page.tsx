import {
  getDashboardData,
  getSupervisorPods,
} from "@/lib/api/sagad-api";
import { CommandCenter } from "@/components/command/command-center";

export default async function Home() {
  const [dashboardData, supervisorPods] = await Promise.all([
    getDashboardData(),
    getSupervisorPods(),
  ]);

  return (
    <CommandCenter data={dashboardData} supervisorPods={supervisorPods} />
  );
}
