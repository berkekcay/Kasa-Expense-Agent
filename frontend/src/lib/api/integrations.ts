// Google account connection, and a mailbox over IMAP with an app password (owner: track INGEST).
import { del, request } from "./client";

export type GoogleStatus = {
  configured: boolean;
  connected: boolean;
  google_email: string | null;
  scopes: string[];
  gmail_access: boolean;
  calendar_access: boolean;
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

/** A mailbox read over IMAP with an app password: purchase emails without Google Cloud. */
export type MailStatus = {
  ready: boolean;
  connected: boolean;
  address: string | null;
  host: string | null;
  folder: string | null;
  last_sync_at: string | null;
  last_error: string | null;
};

export type MailAutoSync = { ran: boolean; result: SyncResult | null };

export type MailConnect = { address: string; password: string; host?: string | null; folder?: string };

export const integrationsApi = {
  googleConnectUrl: () => request<{ url: string }>("/integrations/google/connect"),
  googleStatus: () => request<GoogleStatus>("/integrations/google/status"),
  googleSync: () => request<SyncResult>("/integrations/google/sync", { method: "POST" }),
  googleDisconnect: () => request<void>("/integrations/google", del),
  mailStatus: () => request<MailStatus>("/integrations/mail"),
  mailConnect: (body: MailConnect) =>
    request<MailStatus>("/integrations/mail", { method: "POST", body: JSON.stringify(body) }),
  mailSync: () => request<SyncResult>("/integrations/mail/sync", { method: "POST" }),
  /** Check the mailbox if it is due (the server allows one check every few minutes). */
  mailAutoSync: () => request<MailAutoSync>("/integrations/mail/auto-sync", { method: "POST" }),
  mailDisconnect: () => request<void>("/integrations/mail", del),
};
