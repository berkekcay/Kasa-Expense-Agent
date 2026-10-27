"use client";

import { Fragment, type ReactNode } from "react";
import { useLocale } from "@/lib/i18n";

/** Remounts the app when the language changes, so every label and date re-renders. */
export function LocaleRoot({ children }: { children: ReactNode }) {
  const locale = useLocale();
  return <Fragment key={locale}>{children}</Fragment>;
}
