import type { Metadata } from "next";
import { InviteView } from "@/features/invites/InviteView";

// Invite links are personal: keep them out of search engines.
export const metadata: Metadata = { title: "House invite", robots: { index: false, follow: false } };

// The code is only known at request time, so this route has no static shell to show first
// (the root layout's Nav reads the pathname). Let it render on request instead.
export const instant = false;

export default async function InvitePage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  return <InviteView code={code} />;
}
