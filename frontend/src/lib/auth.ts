// Who is using the app?
//
// - NEXT_PUBLIC_FIREBASE_API_KEY, _AUTH_DOMAIN and _PROJECT_ID set: Firebase Auth with Google
//   sign-in. Requests carry "Authorization: Bearer <Firebase ID token>". The backend must have
//   FIREBASE_PROJECT_ID set to the same project.
// - Not set (local dev): a free-text "dev user" kept in localStorage and sent as X-User-Id.
// - A Kasa account session (see below) wins over both when one is stored.
//
// The Firebase SDK is loaded lazily, so it costs nothing when Firebase is not configured.

import type { Auth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export const firebaseEnabled = Boolean(
  firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId,
);

export type AuthUser = { uid: string; email: string | null; displayName: string | null };

// --- dev user (no Firebase) ----------------------------------------------------------------

const DEV_USER_KEY = "kasa.userId";
export const DEFAULT_USER_ID = "dev-user";
const DEV_USER_EVENT = "kasa:user-changed";

export function getDevUserId(): string {
  if (typeof window === "undefined") return DEFAULT_USER_ID;
  try {
    return window.localStorage.getItem(DEV_USER_KEY) || DEFAULT_USER_ID;
  } catch {
    return DEFAULT_USER_ID;
  }
}

export function setDevUserId(userId: string): void {
  try {
    window.localStorage.setItem(DEV_USER_KEY, userId.trim() || DEFAULT_USER_ID);
  } catch {
    // storage unavailable (private mode); the default user is used instead
  }
  window.dispatchEvent(new Event(DEV_USER_EVENT));
}

export function subscribeDevUser(onChange: () => void): () => void {
  window.addEventListener(DEV_USER_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(DEV_USER_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

// --- Firebase -------------------------------------------------------------------------------

let authPromise: Promise<Auth> | null = null;

function firebaseAuth(): Promise<Auth> {
  authPromise ??= (async () => {
    const [{ getApps, initializeApp }, { getAuth }] = await Promise.all([
      import("firebase/app"),
      import("firebase/auth"),
    ]);
    const app = getApps()[0] ?? initializeApp(firebaseConfig);
    return getAuth(app);
  })();
  return authPromise;
}

let currentUser: AuthUser | null = null;
let authReady = !firebaseEnabled;
const listeners = new Set<() => void>();
let watching = false;

function watchAuthState() {
  if (watching || !firebaseEnabled || typeof window === "undefined") return;
  watching = true;
  void firebaseAuth().then(async (auth) => {
    const { onAuthStateChanged } = await import("firebase/auth");
    onAuthStateChanged(auth, (user) => {
      currentUser = user ? { uid: user.uid, email: user.email, displayName: user.displayName } : null;
      authReady = true;
      listeners.forEach((notify) => notify());
    });
  });
}

/** useSyncExternalStore subscription for the signed-in Firebase user. */
export function subscribeAuthUser(onChange: () => void): () => void {
  watchAuthState();
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

/** The signed-in user (stable object between changes), or null. */
export function getAuthUser(): AuthUser | null {
  return currentUser;
}

export function isAuthReady(): boolean {
  return authReady;
}

export async function signInWithGoogle(): Promise<void> {
  const auth = await firebaseAuth();
  const { GoogleAuthProvider, signInWithPopup } = await import("firebase/auth");
  await signInWithPopup(auth, new GoogleAuthProvider());
}

export async function signOut(): Promise<void> {
  const auth = await firebaseAuth();
  const { signOut: firebaseSignOut } = await import("firebase/auth");
  await firebaseSignOut(auth);
}

/** Fresh ID token for the signed-in user (the SDK refreshes it when it is about to expire). */
export async function getIdToken(): Promise<string | null> {
  if (!firebaseEnabled) return null;
  const auth = await firebaseAuth();
  await auth.authStateReady();
  return auth.currentUser ? auth.currentUser.getIdToken() : null;
}

// --- Kasa account session (email + password + TOTP, or Google sign-in) -------------------------
// The API hands out a session token ("ks_...", 30 days) after the second step. It lives in
// localStorage under kasa.session together with the account's id, so useUserId() can key the
// data views on it. When a session exists it wins over the dev user and over Firebase.

const SESSION_KEY = "kasa.session";
const SESSION_EVENT = "kasa:session-changed";

/** The account part of a token response (the same shape as GET /me). */
export type SessionUser = {
  user_id: string;
  display_name: string;
  email: string | null;
  login_email?: string | null;
  has_password?: boolean;
  google_linked?: boolean;
  totp_enabled?: boolean;
  kind?: "account" | "dev";
};

export type Session = { token: string; userId: string; expiresAt: string | null; user: SessionUser | null };

let sessionRaw: string | null | undefined;
let sessionCache: Session | null = null;

function parseSession(raw: string | null): Session | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<Session>;
    if (typeof value.token !== "string" || !value.token || typeof value.userId !== "string") return null;
    if (value.expiresAt && Date.parse(value.expiresAt) < Date.now()) return null;
    return { token: value.token, userId: value.userId, expiresAt: value.expiresAt ?? null, user: value.user ?? null };
  } catch {
    return null;
  }
}

/** The stored session (a stable object between changes), or null. */
export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(SESSION_KEY);
  } catch {
    raw = null;
  }
  if (raw !== sessionRaw) {
    sessionRaw = raw;
    sessionCache = parseSession(raw);
  }
  return sessionCache;
}

function writeSession(session: Session | null): void {
  try {
    if (session) window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else window.localStorage.removeItem(SESSION_KEY);
  } catch {
    // storage blocked: the session only lasts for this page view
    sessionRaw = session ? JSON.stringify(session) : null;
    sessionCache = session;
  }
  window.dispatchEvent(new Event(SESSION_EVENT));
}

/** Store the session token from /auth/totp/confirm or /auth/login/verify. */
export function signIn(token: string, user: SessionUser, expiresAt: string | null = null): void {
  writeSession({ token, userId: user.user_id, expiresAt, user });
}

/** Forget the session locally (no API call). */
export function clearSession(): void {
  writeSession(null);
}

/** End the session on the server (POST /auth/logout), then forget it here. */
export async function signOutSession(): Promise<void> {
  const session = getSession();
  if (session) {
    try {
      const { API_URL } = await import("@/lib/api/client");
      await fetch(`${API_URL}/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.token}` },
      });
    } catch {
      // offline or already ended: forgetting it locally is what matters
    }
  }
  clearSession();
}

/** The API said 401: a stored session is no longer valid, so drop it (the guard sends the
 *  user to /login). Without a session this does nothing. */
export function onUnauthorized(): void {
  if (getSession()) clearSession();
}

/** useSyncExternalStore subscription for the session (this tab and other tabs). */
export function subscribeSession(onChange: () => void): () => void {
  window.addEventListener(SESSION_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(SESSION_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** The header the API client should send: the session token, else Firebase's Bearer token or
 *  the dev X-User-Id, or nothing. */
export async function authHeader(): Promise<[string, string] | null> {
  const session = getSession();
  if (session) return ["Authorization", `Bearer ${session.token}`];
  if (!firebaseEnabled) return ["X-User-Id", getDevUserId()];
  const token = await getIdToken();
  return token ? ["Authorization", `Bearer ${token}`] : null;
}
