import type { Metadata } from "next";
import { CookiesView } from "@/features/legal/CookiesView";

export const metadata: Metadata = {
  title: "Cookies and storage",
  description: "What Kasa keeps in your browser, and why.",
};

export default function Page() {
  return <CookiesView />;
}
