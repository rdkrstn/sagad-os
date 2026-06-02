import {
  getConversations,
  getPrimaryConversation,
} from "@/lib/api/sagad-api";
import { ConversationReview } from "@/components/conversations/conversation-review";

type ConversationsPageProps = {
  searchParams?: Promise<{
    conversationId?: string | string[];
  }>;
};

export default async function ConversationsPage({
  searchParams,
}: ConversationsPageProps) {
  const params = await searchParams;
  const requestedId = Array.isArray(params?.conversationId)
    ? params?.conversationId[0]
    : params?.conversationId;
  const [conversations, primaryConversation] = await Promise.all([
    getConversations(),
    getPrimaryConversation(),
  ]);
  const selectedConversation = requestedId
    ? conversations.find((conversation) => conversation.id === requestedId)
    : undefined;

  return (
    <ConversationReview
      conversations={conversations}
      primaryConversation={selectedConversation ?? primaryConversation}
    />
  );
}
