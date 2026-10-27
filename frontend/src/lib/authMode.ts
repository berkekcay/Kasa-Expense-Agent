"use client";

// How the server checks who you are, from GET /health (fetched once per page load):
// - "dev": the X-User-Id dev user, and account sessions work too (local default)
// - "accounts": only account sessions; the app sends signed-out visitors to /login
// - "firebase": the older Firebase path
// `status` is "loading" until /health answers and "error" when it could not be reached.

import { useSyncExternalStore } from "react";
import { type AuthMode, health } from "@/lib/api/client";

export type AuthModeState = {
  status: "loading" | "ready" | "error";
  mode: AuthMode | null;
  googleLogin: boolean;
};

const LOADING: AuthModeState = { status: "loading", mode: null, googleLogin: false };

let state: AuthModeState = LOADING;
let started = false;
const listeners = new Set<() => void>();

function set(next: AuthModeState) {
  state = next;
  for (const listener of listeners) listener();
}

function load() {
  if (started) return;
  started = true;
  health().then(
    (h) => set({ status: "ready", mode: h.auth, googleLogin: Boolean(h.google_login) }),
    () => {
      started = false; // try again when the next component mounts
      set({ status: "error", mode: null, googleLogin: false });
    },
  );
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  load();
  return () => {
    listeners.delete(listener);
  };
}

export function useAuthMode(): AuthModeState {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => LOADING,
  );
}

/** Tests only: forget the cached /health answer. */
export function resetAuthModeForTests() {
  state = LOADING;
  started = false;
}
