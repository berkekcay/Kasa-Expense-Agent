import type { Metadata } from "next";
import { NotFoundView } from "@/features/info/NotFoundView";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return <NotFoundView />;
}
