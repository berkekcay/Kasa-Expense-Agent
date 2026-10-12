import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { InboxView } from "@/features/inbox/InboxView";

export const metadata: Metadata = { title: "Inbox" };

export default function Page() {
  return (
    <>
      <PageHeader title="Inbox" subtitle="Possible expenses found in Gmail and statements. Approve or reject each one." />
      <InboxView />
    </>
  );
}
