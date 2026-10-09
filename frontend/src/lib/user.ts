"use client";

import { useSyncExternalStore } from "react";
import { DEFAULT_USER_ID, getUserId, setUserId } from "./api";

// The dev user id lives in localStorage; components re-render when it changes.
const EVENT = "kasa:user-changed";

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useUserId(): string {
  return useSyncExternalStore(subscribe, getUserId, () => DEFAULT_USER_ID);
}

export function switchUser(userId: string) {
  setUserId(userId.trim() || DEFAULT_USER_ID);
  window.dispatchEvent(new Event(EVENT));
}
