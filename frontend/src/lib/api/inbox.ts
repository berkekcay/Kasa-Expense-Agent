// Review queue for expenses found in Gmail and statements (owner: track INGEST).
import { patch, post, query, request } from "./client";
import type { Expense } from "./expenses";

export type ParsedExpense = {
  merchant: string;
  total: string;
  currency: string;
  expense_date: string | null;
  category: string | null;
  items: { description: string; amount: string; quantity: string }[];
};

export type InboxStatus = "pending" | "approved" | "rejected" | "failed" | "ignored";
export type InboxFilter = InboxStatus | "all";

export type InboxItem = {
  id: number;
  source: "email" | "statement";
  external_ref: string;
  received_at: string;
  title: string;
  sender: string | null;
  excerpt: string | null;
  parsed: ParsedExpense | null;
  status: InboxStatus;
  expense_id: number | null;
  error: string | null;
  created_at: string;
  decided_at: string | null;
};

export type InboxBulkResult = {
  results: { item_id: number; status: string; expense_id: number | null; warnings: string[]; error: string | null }[];
  succeeded: number;
  failed: number;
};

export const inboxApi = {
  list: (status: InboxFilter = "pending", limit = 200) => request<InboxItem[]>(`/inbox${query({ status, limit })}`),
  get: (id: number) => request<InboxItem>(`/inbox/${id}`),
  edit: (id: number, parsed: ParsedExpense) => request<InboxItem>(`/inbox/${id}`, patch(parsed)),
  approve: (id: number, parsed?: ParsedExpense) =>
    request<{ item: InboxItem; expense: Expense }>(`/inbox/${id}/approve`, post({ parsed: parsed ?? null })),
  reject: (id: number) => request<InboxItem>(`/inbox/${id}/reject`, { method: "POST" }),
  approveMany: (ids: number[]) => request<InboxBulkResult>("/inbox/approve", post({ ids })),
  rejectMany: (ids: number[]) => request<InboxBulkResult>("/inbox/reject", post({ ids })),
};
