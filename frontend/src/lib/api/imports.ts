// Bank / card statement upload (owner: track INGEST).
import { request, upload } from "./client";
import type { SyncResult } from "./integrations";

export type ImportResult = { lines: number; created: number; duplicates: number; skipped: number; errors: string[] };

export const importsApi = {
  uploadStatement: (file: File) => request<ImportResult>("/imports/statement", upload(file)),
  /** One email saved as .eml: read by the email parser into the inbox, like a synced email. */
  uploadEmail: (file: File) => request<SyncResult>("/imports/email", upload(file)),
};
