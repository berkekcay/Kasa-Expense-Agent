import type { Metadata } from "next";
import { ImportHeader, ImportView } from "@/features/imports/ImportView";

export const metadata: Metadata = { title: "Import a statement" };

export default function Page() {
  return (
    <>
      <ImportHeader />
      <ImportView />
    </>
  );
}
