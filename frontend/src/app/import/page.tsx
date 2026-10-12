import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { ImportView } from "@/features/imports/ImportView";

export const metadata: Metadata = { title: "Import a statement" };

export default function Page() {
  return (
    <>
      <PageHeader title="Import a statement" subtitle="Upload a bank or card statement (CSV or PDF). Lines go to your inbox for review." />
      <ImportView />
    </>
  );
}
