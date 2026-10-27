"use client";

import { createContext, type ReactNode, useCallback, useContext, useMemo, useRef, useState } from "react";
import { useT } from "@/lib/i18n";
import { uiMessages } from "./messages";

type ToastTone = "info" | "success" | "warning" | "error";
type Toast = { id: number; tone: ToastTone; text: string };
type Notify = (text: string, tone?: ToastTone) => void;

const ToastContext = createContext<Notify>(() => {});

/** Shows short messages (budget alerts, saved, failed) in a polite live region. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const tr = useT(uiMessages);

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const notify = useCallback<Notify>(
    (text, tone = "info") => {
      const id = nextId.current++;
      setToasts((t) => [...t.slice(-4), { id, tone, text }]);
      const ms = tone === "warning" || tone === "error" ? 12000 : 6000;
      window.setTimeout(() => dismiss(id), ms);
    },
    [dismiss],
  );

  const value = useMemo(() => notify, [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4 sm:items-end"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.tone === "error" ? "alert" : "status"}
            className={`pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border bg-card px-4 py-3 text-sm shadow-lg ${
              {
                info: "border-border",
                success: "border-positive/50",
                warning: "border-[var(--status-warning)]",
                error: "border-danger/60",
              }[t.tone]
            }`}
          >
            <span
              aria-hidden
              className={`mt-1.5 size-2 shrink-0 rounded-full ${
                {
                  info: "bg-muted",
                  success: "bg-[var(--status-good)]",
                  warning: "bg-[var(--status-warning)]",
                  error: "bg-[var(--status-critical)]",
                }[t.tone]
              }`}
            />
            <p className="min-w-0 flex-1">
              <span className="sr-only">{tr(`tone.${t.tone}`)}: </span>
              {t.text}
            </p>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label={tr("dismissMessage")}
              className="-mr-1 -mt-0.5 h-6 w-6 shrink-0 rounded text-muted hover:text-foreground"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): Notify {
  return useContext(ToastContext);
}

/** Budget alerts and FX notes from a create response, one toast each. */
export function useWarningToasts() {
  const notify = useToast();
  return useCallback(
    (warnings: string[] | undefined) => {
      for (const w of warnings ?? []) {
        notify(w, /budget|exceeded|used/i.test(w) ? "warning" : "info");
      }
    },
    [notify],
  );
}
