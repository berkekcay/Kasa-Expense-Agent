import type { Metadata } from "next";
import { PrivacyView } from "@/features/legal/PrivacyView";

export const metadata: Metadata = {
  title: "Privacy policy",
  description: "How Kasa handles personal data, including the KVKK information notice.",
};

export default function Page() {
  return <PrivacyView />;
}
