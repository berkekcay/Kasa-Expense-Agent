import type { Metadata } from "next";
import { InboxView } from "@/features/inbox/InboxView";

export const metadata: Metadata = { title: "Inbox" };

// The view draws its own page header, because the header actions need client state.
export default function Page() {
  return <InboxView />;
}
