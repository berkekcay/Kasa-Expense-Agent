import type { Metadata } from "next";
import { HelpView } from "@/features/info/HelpView";

export const metadata: Metadata = {
  title: "Help",
  description: "Answers to common questions about using Kasa.",
};

export default function Page() {
  return <HelpView />;
}
