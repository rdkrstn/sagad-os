import { AuditLogConsole } from "@/components/logs/audit-log-console";
import { getAuditEvents } from "@/lib/api/sagad-api";

export default async function LogsPage() {
  const events = await getAuditEvents();

  return <AuditLogConsole events={events} />;
}
