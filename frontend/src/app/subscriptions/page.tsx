import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { SubscriptionsView } from "@/features/subscriptions/SubscriptionsView";

export const metadata: Metadata = { title: "Subscriptions" };

export default function Page() {
  return (
    <>
      <PageHeader title="Subscriptions" subtitle="Recurring charges Kasa found in your expenses." />
      <SubscriptionsView />
    </>
  );
}
