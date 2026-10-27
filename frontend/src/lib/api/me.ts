// The signed-in user's profile: the display name flatmates see, and how they sign in.
import { patch, request } from "./client";

export type Me = {
  user_id: string;
  display_name: string;
  email: string | null;
  /** The account's sign-in email (accounts mode); the fields below are absent on older servers. */
  login_email?: string | null;
  has_password?: boolean;
  google_linked?: boolean;
  totp_enabled?: boolean;
  /** "account" for a Kasa account session, "dev" for the X-User-Id dev user. */
  kind?: "account" | "dev";
};

export const meApi = {
  get: () => request<Me>("/me"),
  setDisplayName: (displayName: string) => request<Me>("/me", patch({ display_name: displayName })),
};
