import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { ChatView } from "@/features/chat/ChatView";

export const metadata: Metadata = { title: "Ask Kasa" };

export default function ChatPage() {
  return (
    <>
      <PageHeader title="Ask Kasa" subtitle="Questions in, answers and charts out. Kasa only sees your own data." />
      <ChatView />
    </>
  );
}
