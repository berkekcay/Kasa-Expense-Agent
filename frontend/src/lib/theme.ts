"use client";

import { useSyncExternalStore } from "react";

// Light, dark or "system" (follow the OS). The choice lives in localStorage and is applied
// as html[data-theme] by THEME_SCRIPT before the first paint, so there is no flash.

export type ThemeChoice = "system" | "light" | "dark";
const KEY = "kasa.theme";
const listeners = new Set<() => void>();

/** Runs inline in <head>; keep it tiny and dependency free. */
export const THEME_SCRIPT = `try{var t=localStorage.getItem("${KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

function read(): ThemeChoice {
  try {
    const t = window.localStorage.getItem(KEY);
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

export function setTheme(choice: ThemeChoice) {
  try {
    if (choice === "system") window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, choice);
  } catch {
    // storage blocked; the choice still applies to this page view
  }
  if (choice === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = choice;
  for (const l of listeners) l();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", listener);
  return () => {
    listeners.delete(listener);
    media.removeEventListener("change", listener);
  };
}

export function useThemeChoice(): ThemeChoice {
  return useSyncExternalStore(subscribe, read, () => "system");
}

/** The theme actually shown, for code that cannot use CSS variables directly. */
export function useResolvedTheme(): "light" | "dark" {
  const choice = useThemeChoice();
  const systemDark = useSyncExternalStore(
    subscribe,
    () => window.matchMedia("(prefers-color-scheme: dark)").matches,
    () => false,
  );
  if (choice === "system") return systemDark ? "dark" : "light";
  return choice;
}
