// Saved reports (track REPORT): charts kept from the chat, run again on fresh data.
import type { ChartSpec } from "./chat";
import { patch, post, request, requestBlob } from "./client";

export type SavedReport = {
  id: number;
  title: string;
  question: string | null;
  chart_type: string;
  pinned: boolean;
  created_at: string;
  last_run_at: string | null;
};

export type ReportRun = {
  report: SavedReport;
  chart: ChartSpec | null;
  columns: string[];
  rows: Record<string, string | number | boolean | null>[];
  truncated: boolean;
  run_at: string;
};

export const reportsApi = {
  save: (messageId: number, title?: string) => request<SavedReport>("/reports", post({ message_id: messageId, title })),
  list: (pinnedOnly = false) => request<SavedReport[]>(`/reports${pinnedOnly ? "?pinned=true" : ""}`),
  run: (id: number) => request<ReportRun>(`/reports/${id}/run`),
  update: (id: number, body: { title?: string; pinned?: boolean }) => request<SavedReport>(`/reports/${id}`, patch(body)),
  remove: (id: number) => request<void>(`/reports/${id}`, { method: "DELETE" }),
  exportCsv: (id: number) => requestBlob(`/reports/${id}/export.csv`),
};
