// Receipt photo upload -> receipt agent (shared).
import { request, upload } from "./client";
import type { Expense } from "./expenses";

export type ReceiptResult = { expense: Expense; agent_message: string; warnings: string[] };

export const receiptsApi = {
  uploadReceipt: (file: File) => request<ReceiptResult>("/receipts", upload(file)),
};
