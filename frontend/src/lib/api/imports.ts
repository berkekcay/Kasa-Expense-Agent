// Bank / card statement upload (owner: track INGEST).
import { request, upload } from "./client";

export type ImportResult = { lines: number; created: number; duplicates: number; skipped: number; errors: string[] };

export const importsApi = {
  uploadStatement: (file: File) => request<ImportResult>("/imports/statement", upload(file)),
};
