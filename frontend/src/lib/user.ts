"use client";

import { useSyncExternalStore } from "react";
import {
  type AuthUser,
  DEFAULT_USER_ID,
  firebaseEnabled,
  getAuthUser,
  getDevUserId,
  setDevUserId,
  subscribeAuthUser,
  subscribeDevUser,
} from "./auth";

const noUser = () => null;
const noop = () => () => {};

/** The signed-in Firebase user (null when signed out or when Firebase is not configured). */
export function useAuthUser(): AuthUser | null {
  return useSyncExternalStore(firebaseEnabled ? subscribeAuthUser : noop, getAuthUser, noUser);
}

/** Id of whoever is acting now. Views use it as an effect dependency to refetch on switch.
 *  With Firebase it is the uid ("" while signed out); in dev mode it is the dev user. */
export function useUserId(): string {
  const devUser = useSyncExternalStore(subscribeDevUser, getDevUserId, () => DEFAULT_USER_ID);
  const authUser = useAuthUser();
  return firebaseEnabled ? (authUser?.uid ?? "") : devUser;
}

/** Dev mode only: act as another user. */
export function switchUser(userId: string) {
  setDevUserId(userId);
}
