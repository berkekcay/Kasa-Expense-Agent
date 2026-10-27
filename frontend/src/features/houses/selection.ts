"use client";

// Which house the house page should open next. Joining with an invite link sets it, so the
// person lands on the house they just joined even if they were already in another one.
import { useSyncExternalStore } from "react";

let preferred: number | null = null;
const listeners = new Set<() => void>();

export function preferHouse(houseId: number) {
  preferred = houseId;
  for (const l of listeners) l();
}

export function usePreferredHouse(): number | null {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => preferred,
    () => null,
  );
}
