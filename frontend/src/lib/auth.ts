// Who is using the app?
//
// - NEXT_PUBLIC_FIREBASE_API_KEY, _AUTH_DOMAIN and _PROJECT_ID set: Firebase Auth with Google
//   sign-in. Requests carry "Authorization: Bearer <Firebase ID token>". The backend must have
//   FIREBASE_PROJECT_ID set to the same project.
// - Not set (local dev): a free-text "dev user" kept in localStorage and sent as X-User-Id.
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

/** The header the API client should send: Bearer token, dev X-User-Id, or nothing. */
export async function authHeader(): Promise<[string, string] | null> {
  if (!firebaseEnabled) return ["X-User-Id", getDevUserId()];
  const token = await getIdToken();
  return token ? ["Authorization", `Bearer ${token}`] : null;
}
