import { ApprovalQueueConsole } from "@/components/approvals/approval-queue-console";
import { getQueueConversations } from "@/lib/api/sagad-api";

export default async function ApprovalsPage() {
  const conversations = await getQueueConversations();

  return <ApprovalQueueConsole conversations={conversations} />;
}
