"use client";

// A drag-and-drop file zone with real file inputs behind its buttons. Used by the receipt and
// statement pages. Clicking the empty part of the zone opens the first picker; keyboard users
// reach each picker through its button.

import { type ChangeEvent, type DragEvent, type MouseEvent, type ReactNode, useRef, useState } from "react";
import { getLocale, useT } from "@/lib/i18n";
import { messages } from "./messages";

export type Picker = {
  id: string;
  label: string;
  icon: ReactNode;
  accept: string;
  /** Opens the camera on phones. */
  capture?: "environment" | "user";
  primary?: boolean;
  /** Only shown on touch devices (the camera button). */
  touchOnly?: boolean;
};

const BUTTON =
  "inline-flex h-9 cursor-pointer items-center justify-center gap-1.5 rounded-lg px-3.5 text-sm font-medium whitespace-nowrap transition [&>svg]:size-4 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--accent)] peer-disabled:cursor-not-allowed peer-disabled:opacity-50";
const PRIMARY = "bg-accent text-accent-foreground shadow-card hover:brightness-110";
const GHOST = "border border-border bg-card shadow-card hover:border-border-strong hover:bg-card-hover";

export function Dropzone({
  pickers,
  onFile,
  disabled = false,
  icon,
  title,
  hint,
  children,
}: {
  pickers: Picker[];
  onFile: (file: File) => void;
  disabled?: boolean;
  icon: ReactNode;
  title: string;
  hint?: ReactNode;
  /** Shown instead of the prompt once a file is chosen (a preview or file row). */
  children?: ReactNode;
}) {
  const t = useT(messages);
  const [over, setOver] = useState(false);
  const depth = useRef(0);
  const first = useRef<HTMLInputElement | null>(null);
  const filled = Boolean(children);

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0];
    e.target.value = ""; // picking the same file again still fires change
    if (picked) onFile(picked);
  }

  function onDragEnter(e: DragEvent) {
    e.preventDefault();
    if (disabled) return;
    depth.current += 1;
    setOver(true);
  }

  function onDragOver(e: DragEvent) {
    e.preventDefault();
    e.dataTransfer.dropEffect = disabled ? "none" : "copy";
  }

  function onDragLeave() {
    depth.current = Math.max(0, depth.current - 1);
    if (depth.current === 0) setOver(false);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    depth.current = 0;
    setOver(false);
    if (disabled) return;
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) onFile(dropped);
  }

  function onZoneClick(e: MouseEvent<HTMLDivElement>) {
    if (disabled || filled) return;
    if ((e.target as HTMLElement).closest("label, button, a, input")) return;
    first.current?.click();
  }

  return (
    <div
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={onZoneClick}
      className={`relative flex flex-col items-center gap-4 rounded-2xl border-2 border-dashed text-center transition ${
        filled ? "p-3 sm:p-4" : "cursor-pointer px-5 py-10"
      } ${
        over
          ? "border-accent bg-accent-soft"
          : disabled
            ? "border-border opacity-60"
            : "border-border bg-foreground/[0.015] hover:border-border-strong"
      } ${disabled ? "cursor-not-allowed" : ""}`}
    >
      {filled ? (
        children
      ) : (
        <>
          <span
            aria-hidden
            className={`flex size-12 items-center justify-center rounded-2xl transition [&>svg]:size-6 ${
              over ? "bg-accent text-accent-foreground" : "bg-accent-soft text-accent"
            }`}
          >
            {icon}
          </span>
          <div>
            <p className="text-[15px] font-semibold">{over ? t("dropToAdd") : title}</p>
            {hint && <p className="mt-1 text-sm text-muted">{hint}</p>}
          </div>
        </>
      )}
      <div className="flex flex-wrap justify-center gap-2">
        {pickers.map((p, i) => (
          <span key={p.id} className={p.touchOnly ? "pointer-fine:hidden" : ""}>
            <input
              ref={i === 0 ? first : undefined}
              id={p.id}
              type="file"
              accept={p.accept}
              capture={p.capture}
              onChange={onChange}
              disabled={disabled}
              className="peer sr-only"
            />
            <label htmlFor={p.id} className={`${BUTTON} ${p.primary ? PRIMARY : GHOST}`}>
              {p.icon}
              {p.label}
            </label>
          </span>
        ))}
      </div>
    </div>
  );
}

/** "2481920" bytes -> "2.4 MB" ("2,4 MB" in Turkish). Display only. */
export function fileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  const mb = (bytes / (1024 * 1024)).toFixed(1);
  return `${getLocale() === "tr" ? mb.replace(".", ",") : mb} MB`;
}

/** Elapsed time and a time-based bar for slow model calls. The bar is an estimate, not real progress. */
export function SlowProgress({
  title,
  elapsed,
  expected = 120,
  children,
}: {
  title: string;
  elapsed: number;
  expected?: number;
  children?: ReactNode;
}) {
  const t = useT(messages);
  const width = Math.min(95, 4 + (elapsed / expected) * 91);
  return (
    <div className="rounded-xl border border-border bg-foreground/[0.02] p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <span aria-hidden className="inline-block size-4 animate-spin rounded-full border-2 border-accent border-r-transparent motion-reduce:animate-none" />
        {title}
        <span aria-hidden className="ml-auto text-xs font-normal text-muted tabular-nums">
          {t("seconds", { n: elapsed })}
        </span>
      </div>
      <div aria-hidden className="mt-3 h-1.5 overflow-hidden rounded-full bg-foreground/[0.07]">
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-1000 ease-linear motion-reduce:transition-none"
          style={{ width: `${width}%` }}
        />
      </div>
      {children && <div className="mt-2.5 text-xs text-muted">{children}</div>}
    </div>
  );
}
