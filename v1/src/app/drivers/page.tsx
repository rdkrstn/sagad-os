import { getContactDrivers } from "@/lib/api/sagad-api";
import { DriverAnalytics } from "@/components/drivers/driver-analytics";

// TODO(product-nav): Decide whether this legacy driver-analysis route remains an advanced admin surface outside the product nav.
export default async function DriversPage() {
  const drivers = await getContactDrivers();

  return <DriverAnalytics drivers={drivers} />;
}
