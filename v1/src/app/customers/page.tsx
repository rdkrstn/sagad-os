import { CustomerConsole } from "@/components/customers/customer-console";
import { getCustomers } from "@/lib/api/sagad-api";

export default async function CustomersPage() {
  const customers = await getCustomers();

  return <CustomerConsole customers={customers} />;
}
