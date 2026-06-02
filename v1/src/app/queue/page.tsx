import { getQueueConversations } from "@/lib/api/sagad-api";
import { AttentionQueue } from "@/components/queue/attention-queue";

export default async function QueuePage() {
  const conversations = await getQueueConversations();

  return <AttentionQueue conversations={conversations} />;
}
