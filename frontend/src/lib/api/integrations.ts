// Google account connection (owner: track INGEST).
import { del, request } from "./client";

export type GoogleStatus = {
  configured: boolean;
  connected: boolean;
  google_email: string | null;
  scopes: string[];
  gmail_watch_expires_at: string | null;
};

export type SyncResult = {
  fetched: number;
  created: number;
  ignored: number;
  duplicates: number;
  failed: number;
  error: string | null;
};

export const integrationsApi = {
  googleConnectUrl: () => request<{ url: string }>("/integrations/google/connect"),
  googleStatus: () => request<GoogleStatus>("/integrations/google/status"),
  googleSync: () => request<SyncResult>("/integrations/google/sync", { method: "POST" }),
  googleDisconnect: () => request<void>("/integrations/google", del),
};
