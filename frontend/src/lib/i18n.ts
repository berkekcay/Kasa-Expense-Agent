"use client";

// Turkish and English for the UI. Each feature keeps its own messages next to its code
// (`features/<x>/messages.ts`) built with `defineMessages`, so teams never edit one shared
// file. The locale lives in localStorage; `LOCALE_SCRIPT` sets <html lang> before the first
// paint. The server always renders English; a Turkish user's browser switches right after
// hydration.

import { useSyncExternalStore } from "react";

export type Locale = "en" | "tr";
export const LOCALES: { value: Locale; label: string }[] = [
  { value: "en", label: "English" },
  { value: "tr", label: "Türkçe" },
];

const KEY = "kasa.locale";
const listeners = new Set<() => void>();
let current: Locale = "en";
let loaded = false;

/** Runs inline in <head>: the saved choice, else the browser language. */
export const LOCALE_SCRIPT = `try{var l=localStorage.getItem("${KEY}");if(l!=="en"&&l!=="tr")l=(navigator.language||"").toLowerCase().indexOf("tr")===0?"tr":"en";document.documentElement.lang=l}catch(e){}`;

function read(): Locale {
  if (!loaded && typeof window !== "undefined") {
    loaded = true;
    try {
      const saved = window.localStorage.getItem(KEY);
      current =
        saved === "en" || saved === "tr" ? saved : navigator.language.toLowerCase().startsWith("tr") ? "tr" : "en";
    } catch {
      current = "en";
    }
  }
  return current;
}

/** The locale for code outside React (format helpers). */
export function getLocale(): Locale {
  return typeof window === "undefined" ? "en" : read();
}

export function setLocale(locale: Locale) {
  current = locale;
  loaded = true;
  try {
    window.localStorage.setItem(KEY, locale);
  } catch {
    // storage blocked; the choice still applies to this page view
  }
  document.documentElement.lang = locale;
  for (const l of listeners) l();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useLocale(): Locale {
  return useSyncExternalStore(subscribe, read, () => "en");
}

type Vars = Record<string, string | number>;
type Message = string | ((vars: Vars) => string);
type Dict = Record<string, Message>;

/**
 * Messages for one feature. Turkish must have exactly the English keys, so a missing
 * translation is a type error.
 *
 *   const messages = defineMessages({
 *     en: { title: "Budgets", count: ({ n }) => (n === 1 ? "1 budget" : `${n} budgets`) },
 *     tr: { title: "Bütçeler", count: ({ n }) => `${n} bütçe` },
 *   });
 */
export function defineMessages<E extends Dict>(m: { en: E; tr: { [K in keyof E]: Message } }) {
  return m as { en: E; tr: Record<keyof E, Message> };
}

function render(message: Message, vars: Vars = {}): string {
  if (typeof message === "function") return message(vars);
  return message.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? `{${k}}`));
}

/** `t("key", { n: 3 })` for the current locale. */
export function useT<E extends Dict>(messages: { en: E; tr: Record<keyof E, Message> }) {
  const locale = useLocale();
  return (key: keyof E & string, vars?: Vars) => render((messages[locale] as Dict)[key] ?? messages.en[key], vars);
}

/** The same outside React, e.g. in chart tooltip formatters. */
export function translate<E extends Dict>(
  messages: { en: E; tr: Record<keyof E, Message> },
  key: keyof E & string,
  vars?: Vars,
): string {
  return render((messages[getLocale()] as Dict)[key] ?? messages.en[key], vars);
}
