import type { Metadata } from "next";
import { TermsView } from "@/features/legal/TermsView";

export const metadata: Metadata = {
  title: "Terms of use",
  description: "The rules for using Kasa, a student project.",
};

export default function Page() {
  return <TermsView />;
}
