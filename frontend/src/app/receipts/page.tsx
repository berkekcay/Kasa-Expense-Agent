import type { Metadata } from "next";
import { ReceiptUpload, ReceiptsHeader } from "@/features/receipts/ReceiptUpload";

export const metadata: Metadata = { title: "Receipt" };

export default function ReceiptsPage() {
  return (
    <>
      <ReceiptsHeader />
      <ReceiptUpload />
    </>
  );
}
