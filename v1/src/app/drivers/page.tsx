import { getContactDrivers } from "@/lib/api/sagad-api";
import { DriverAnalytics } from "@/components/drivers/driver-analytics";

export default async function DriversPage() {
  const drivers = await getContactDrivers();

  return <DriverAnalytics drivers={drivers} />;
}
