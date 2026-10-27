"use client";

import { useSyncExternalStore } from "react";
import {
  type AuthUser,
  DEFAULT_USER_ID,
  type Session,
  firebaseEnabled,
  getAuthUser,
  getDevUserId,
  getSession,
  setDevUserId,
  subscribeAuthUser,
  subscribeDevUser,
  subscribeSession,
} from "./auth";

const noUser = () => null;
const noop = () => () => {};

/** The signed-in Firebase user (null when signed out or when Firebase is not configured). */
export function useAuthUser(): AuthUser | null {
  return useSyncExternalStore(firebaseEnabled ? subscribeAuthUser : noop, getAuthUser, noUser);
}

/** The Kasa account session (token and user), or null when nobody signed in with an account. */
export function useSession(): Session | null {
  return useSyncExternalStore(subscribeSession, getSession, noUser);
}

/** Id of whoever is acting now. Views use it as an effect dependency to refetch on switch.
 *  A signed-in Kasa account wins; otherwise with Firebase it is the uid ("" while signed out),
 *  and in dev mode it is the dev user. */
export function useUserId(): string {
  const devUser = useSyncExternalStore(subscribeDevUser, getDevUserId, () => DEFAULT_USER_ID);
  const authUser = useAuthUser();
  const session = useSession();
  if (session) return session.userId;
  return firebaseEnabled ? (authUser?.uid ?? "") : devUser;
}

/** Dev mode only: act as another user. */
export function switchUser(userId: string) {
  setDevUserId(userId);
}
