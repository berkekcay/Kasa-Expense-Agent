import type { Metadata } from "next";
import { SubscriptionsView } from "@/features/subscriptions/SubscriptionsView";

export const metadata: Metadata = { title: "Subscriptions" };

// The view draws its own page header, because the header actions need client state.
export default function Page() {
  return <SubscriptionsView />;
}
