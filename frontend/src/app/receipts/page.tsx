import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { ReceiptUpload } from "@/features/receipts/ReceiptUpload";

export const metadata: Metadata = { title: "Receipt" };

export default function ReceiptsPage() {
  return (
    <>
      <PageHeader title="Scan a receipt" subtitle="Take or upload a photo. Kasa reads it and saves the expense." />
      <ReceiptUpload />
    </>
  );
}
