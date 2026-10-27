import type { Metadata } from "next";
import { ChatHeader, ChatView } from "@/features/chat/ChatView";

export const metadata: Metadata = { title: "Ask Kasa" };

export default function ChatPage() {
  return (
    <>
      <ChatHeader />
      <ChatView />
    </>
  );
}
