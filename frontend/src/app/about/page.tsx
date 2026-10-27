import type { Metadata } from "next";
import { AboutView } from "@/features/info/AboutView";

export const metadata: Metadata = {
  title: "About",
  description: "What Kasa is, how its AI works and who built it.",
};

export default function Page() {
  return <AboutView />;
}
