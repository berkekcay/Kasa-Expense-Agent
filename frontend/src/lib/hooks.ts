"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { errorMessage } from "@/lib/errors";
import { useUserId } from "@/lib/user";

const noopSubscribe = () => () => {};

/** False during server rendering and hydration, true afterwards. Gate anything that reads
 *  the clock or browser storage behind it so the prerendered HTML stays deterministic. */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

type State<T> = { key: string | null; data: T | null; error: string | null };

/**
 * Loads data from the API and reloads when the acting user or `deps` change.
 * - `loading` is true until the request for the current deps settles.
 * - The previous data stays visible while a reload runs (no layout jump).
 * - `deps` must be primitives (strings, numbers, booleans, null).
 */
export function useApi<T>(load: () => Promise<T>, deps: ReadonlyArray<string | number | boolean | null | undefined>) {
  const userId = useUserId();
  const [nonce, setNonce] = useState(0);
  const key = JSON.stringify([userId, nonce, ...deps]);
  const loadRef = useRef(load);
  useEffect(() => {
    loadRef.current = load;
  });
  const [state, setState] = useState<State<T>>({ key: null, data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    loadRef.current().then(
      (data) => {
        if (!cancelled) setState({ key, data, error: null });
      },
      (e: unknown) => {
        if (!cancelled) setState((s) => ({ key, data: s.data, error: errorMessage(e) }));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [key]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const setData = useCallback((update: (prev: T | null) => T | null) => {
    setState((s) => ({ ...s, data: update(s.data) }));
  }, []);

  return {
    data: state.data,
    error: state.key === key ? state.error : null,
    loading: state.key !== key,
    reload,
    setData,
  };
}

/** Seconds since `running` became true; 0 while idle. For honest long-wait messages. */
export function useElapsed(running: boolean): number {
  const [elapsed, setElapsed] = useState(0);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  useEffect(() => {
    if (!running) return;
    const start = Date.now();
    const id = window.setInterval(() => {
      setStartedAt(start);
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => {
      window.clearInterval(id);
      setStartedAt(null);
      setElapsed(0);
    };
  }, [running]);
  return running && startedAt !== null ? elapsed : 0;
}
