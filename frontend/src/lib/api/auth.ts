// Kasa accounts: register, password login, Google Authenticator (TOTP) and sessions.
// The first step (register, login or Google) returns a pending token that lives 10 minutes;
// the TOTP step trades it for a session token ("ks_...", 30 days). See lib/auth.ts for storage.
import { API_URL, del, post, query, request } from "./client";
import type { Me } from "./me";

export type AuthStep = "totp" | "totp_setup";
export type Pending = { pending_token: string; step: AuthStep };
export type TotpSetup = { secret: string; otpauth_uri: string; qr_svg: string };
export type SignedIn = { token: string; expires_at: string; user: Me };
export type Confirmed = SignedIn & { recovery_codes: string[] };
export type SessionInfo = {
  id: string;
  user_agent: string | null;
  created_at: string;
  last_seen_at: string | null;
  expires_at: string;
  current: boolean;
};

export type RegisterInput = { email: string; password: string; display_name: string; accept_terms: true };

export const authApi = {
  register: (input: RegisterInput) => request<Pending>("/auth/register", post(input)),
  login: (email: string, password: string) => request<Pending>("/auth/login", post({ email, password })),
  totpSetup: (pendingToken: string) => request<TotpSetup>("/auth/totp/setup", post({ pending_token: pendingToken })),
  totpConfirm: (pendingToken: string, code: string) =>
    request<Confirmed>("/auth/totp/confirm", post({ pending_token: pendingToken, code })),
  verifyCode: (pendingToken: string, code: string) =>
    request<SignedIn>("/auth/login/verify", post({ pending_token: pendingToken, code })),
  verifyRecoveryCode: (pendingToken: string, recoveryCode: string) =>
    request<SignedIn>("/auth/login/verify", post({ pending_token: pendingToken, recovery_code: recoveryCode })),
  sessions: () => request<SessionInfo[]>("/auth/sessions"),
  revokeSession: (id: string) => request<void>(`/auth/sessions/${encodeURIComponent(id)}`, del),
  newRecoveryCodes: (code: string) => request<{ recovery_codes: string[] }>("/auth/recovery-codes", post({ code })),
  changePassword: (currentPassword: string, newPassword: string, code: string) =>
    request<void>("/auth/password", post({ current_password: currentPassword, new_password: newPassword, code })),
  /** Full-page redirect target for "Continue with Google". */
  googleStartUrl: (next: string) => `${API_URL}/auth/google/start${query({ next })}`,
};
