"use client";

// Month and date pickers. Native <input type="month"> is a plain text box in Firefox and
// Safari, and the native date popup looks different in every browser, so Kasa draws its own.
// Values are ISO strings ("2026-10", "2026-10-27"); no Date objects leave this file.

import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight, X } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import { common } from "@/lib/commonMessages";
import { formatDate, longMonthNames, monthNames } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { pickerMessages } from "./messages";

const pad = (n: number) => String(n).padStart(2, "0");
const ym = (y: number, m: number) => `${y}-${pad(m)}`; // m is 1-12
const ymd = (y: number, m: number, d: number) => `${y}-${pad(m)}-${pad(d)}`;

function parseYm(s: string): [number, number] | null {
  const m = /^(\d{4})-(\d{2})/.exec(s);
  return m ? [Number(m[1]), Number(m[2])] : null;
}

function shiftMonth(value: string, by: number): string {
  const [y, m] = parseYm(value) ?? [2026, 1];
  const index = y * 12 + (m - 1) + by;
  return ym(Math.floor(index / 12), (index % 12) + 1);
}

function localToday(): string {
  const d = new Date();
  return ymd(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

/** Closes a popover on outside click and Escape. */
function usePopover() {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return { open, setOpen, root };
}

function Popover({ children, align = "left" }: { children: ReactNode; align?: "left" | "right" }) {
  return (
    <div
      className={`animate-pop absolute top-full z-40 mt-2 w-72 rounded-xl border border-border bg-card p-3 shadow-pop ${align === "right" ? "right-0" : "left-0"}`}
    >
      {children}
    </div>
  );
}

const ICON_BUTTON =
  "inline-flex size-8 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 hover:text-foreground disabled:pointer-events-none disabled:opacity-30";

/**
 * Month switcher: previous / next arrows around a button that opens a year + month grid.
 * `max` (YYYY-MM) disables later months, e.g. the current month on the dashboard.
 */
export function MonthPicker({
  value,
  onChange,
  max,
  label: labelProp,
  align = "left",
}: {
  value: string;
  onChange: (month: string) => void;
  max?: string;
  label?: string;
  align?: "left" | "right";
}) {
  const { open, setOpen, root } = usePopover();
  const [y, m] = parseYm(value) ?? [2026, 1];
  const [year, setYear] = useState(y);
  const id = useId();
  const after = (s: string) => (max ? s > max : false);
  const t = useT(pickerMessages);
  const tc = useT(common);
  const label = labelProp ?? tc("month");
  const longName = longMonthNames()[m - 1];

  return (
    <div ref={root} className="relative inline-flex items-center rounded-lg border border-border bg-card shadow-card">
      <button type="button" aria-label={t("previousMonth")} className={ICON_BUTTON} onClick={() => onChange(shiftMonth(value, -1))}>
        <ChevronLeft className="size-4" />
      </button>
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={id}
        aria-label={t("current", { label, month: longName, year: y })}
        onClick={() => {
          setYear(y);
          setOpen((o) => !o);
        }}
        className="inline-flex h-8 min-w-36 items-center justify-center gap-2 px-2 text-sm font-medium hover:text-accent"
      >
        <CalendarDays aria-hidden className="size-4 text-muted" />
        {longName} {y}
        <ChevronDown aria-hidden className="size-3.5 text-muted" />
      </button>
      <button
        type="button"
        aria-label={t("nextMonth")}
        className={ICON_BUTTON}
        disabled={after(shiftMonth(value, 1))}
        onClick={() => onChange(shiftMonth(value, 1))}
      >
        <ChevronRight className="size-4" />
      </button>
      {open && (
        <Popover align={align}>
          <div id={id} role="dialog" aria-label={t("pickMonth", { label })}>
            <div className="mb-2 flex items-center justify-between">
              <button type="button" aria-label={t("previousYear")} className={ICON_BUTTON} onClick={() => setYear(year - 1)}>
                <ChevronLeft className="size-4" />
              </button>
              <span className="text-sm font-semibold tabular-nums">{year}</span>
              <button
                type="button"
                aria-label={t("nextYear")}
                className={ICON_BUTTON}
                disabled={after(ym(year + 1, 1))}
                onClick={() => setYear(year + 1)}
              >
                <ChevronRight className="size-4" />
              </button>
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              {monthNames().map((name, i) => {
                const v = ym(year, i + 1);
                const selected = v === ym(y, m);
                return (
                  <button
                    key={name}
                    type="button"
                    disabled={after(v)}
                    aria-pressed={selected}
                    onClick={() => {
                      onChange(v);
                      setOpen(false);
                    }}
                    className={`h-9 rounded-lg text-sm transition disabled:opacity-30 ${selected ? "bg-accent font-semibold text-accent-foreground" : "hover:bg-foreground/5"}`}
                  >
                    {name}
                  </button>
                );
              })}
            </div>
          </div>
        </Popover>
      )}
    </div>
  );
}

/** "2026-10-27" -> "27 Oct 2026" (month name in the UI language). */
function formatDay(iso: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) ? formatDate(iso) : iso;
}

/** A calendar for one month, Monday first. */
function Calendar({
  value,
  onPick,
  min,
  max,
}: {
  value: string;
  onPick: (day: string) => void;
  min?: string;
  max?: string;
}) {
  const today = localToday();
  const [view, setView] = useState(() => (value || today).slice(0, 7));
  const [focus, setFocus] = useState(() => value || today);
  const grid = useRef<HTMLDivElement | null>(null);
  const [y, m] = parseYm(view) ?? [2026, 1];
  const first = new Date(Date.UTC(y, m - 1, 1));
  const lead = (first.getUTCDay() + 6) % 7; // Monday = 0
  const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const outside = (d: string) => (min ? d < min : false) || (max ? d > max : false);
  const t = useT(pickerMessages);
  const monthTitle = `${longMonthNames()[m - 1]} ${y}`;

  useEffect(() => {
    grid.current?.querySelector<HTMLButtonElement>(`[data-day="${focus}"]`)?.focus();
  }, [focus]);

  function move(by: number) {
    const p = /^(\d{4})-(\d{2})-(\d{2})$/.exec(focus);
    if (!p) return;
    const d = new Date(Date.UTC(Number(p[1]), Number(p[2]) - 1, Number(p[3]) + by));
    const next = ymd(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
    setView(next.slice(0, 7));
    setFocus(next);
  }

  function onKeyDown(e: KeyboardEvent) {
    const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[e.key];
    if (step) {
      e.preventDefault();
      move(step);
    }
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <button type="button" aria-label={t("previousMonth")} className={ICON_BUTTON} onClick={() => setView(shiftMonth(view, -1))}>
          <ChevronLeft className="size-4" />
        </button>
        <span className="text-sm font-semibold">{monthTitle}</span>
        <button type="button" aria-label={t("nextMonth")} className={ICON_BUTTON} onClick={() => setView(shiftMonth(view, 1))}>
          <ChevronRight className="size-4" />
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs text-muted" aria-hidden>
        {t("weekdays").split(" ").map((d) => (
          <span key={d} className="py-1">
            {d}
          </span>
        ))}
      </div>
      <div ref={grid} role="grid" aria-label={monthTitle} className="grid grid-cols-7 gap-1" onKeyDown={onKeyDown}>
        {Array.from({ length: lead }, (_, i) => (
          <span key={`lead-${i}`} />
        ))}
        {Array.from({ length: days }, (_, i) => {
          const day = ymd(y, m, i + 1);
          const selected = day === value;
          const isToday = day === today;
          return (
            <button
              key={day}
              type="button"
              data-day={day}
              tabIndex={day === focus ? 0 : -1}
              disabled={outside(day)}
              aria-pressed={selected}
              aria-label={formatDay(day)}
              onClick={() => onPick(day)}
              className={`h-9 rounded-lg text-sm tabular-nums transition disabled:opacity-25 ${
                selected
                  ? "bg-accent font-semibold text-accent-foreground"
                  : isToday
                    ? "font-semibold text-accent ring-1 ring-accent/40 hover:bg-accent/10"
                    : "hover:bg-foreground/5"
              }`}
            >
              {i + 1}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * A date field. Works in forms (renders a hidden input with `name`) and as a controlled
 * input (`value` + `onChange`). Empty means "not set"; `placeholder` says what that means.
 */
export function DatePicker({
  label,
  name,
  value: controlled,
  defaultValue = "",
  onChange,
  required,
  min,
  max,
  hint,
  placeholder,
  clearable = true,
  className = "",
  hideLabel = false,
}: {
  label: string;
  name?: string;
  value?: string;
  defaultValue?: string;
  onChange?: (day: string) => void;
  required?: boolean;
  min?: string;
  max?: string;
  hint?: string;
  placeholder?: string;
  clearable?: boolean;
  className?: string;
  hideLabel?: boolean;
}) {
  const [own, setOwn] = useState(defaultValue);
  const value = controlled ?? own;
  const { open, setOpen, root } = usePopover();
  const id = useId();
  const t = useT(pickerMessages);
  const tc = useT(common);

  function pick(day: string) {
    if (controlled === undefined) setOwn(day);
    onChange?.(day);
    setOpen(false);
  }

  return (
    <div className={`flex min-w-0 flex-col gap-1 text-sm ${className}`}>
      <span id={`${id}-label`} className={hideLabel ? "sr-only" : "text-muted"}>
        {label}
        {required && <span aria-hidden> *</span>}
      </span>
      <div ref={root} className="relative">
        <button
          type="button"
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-labelledby={`${id}-label ${id}-value`}
          onClick={() => setOpen((o) => !o)}
          className="flex h-9 w-full min-w-0 items-center gap-2 rounded-lg border border-border bg-background px-3 text-left text-sm outline-none hover:border-border-strong focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/30"
        >
          <CalendarDays aria-hidden className="size-4 shrink-0 text-muted" />
          <span id={`${id}-value`} className={`flex-1 truncate ${value ? "" : "text-muted"}`}>
            {value ? formatDay(value) : (placeholder ?? t("placeholder"))}
          </span>
        </button>
        {clearable && !required && value && (
          <button
            type="button"
            aria-label={t("clear", { label })}
            onClick={() => pick("")}
            className="absolute top-1/2 right-1.5 inline-flex size-6 -translate-y-1/2 items-center justify-center rounded-md text-muted hover:bg-foreground/5 hover:text-foreground"
          >
            <X className="size-3.5" />
          </button>
        )}
        {name && <input type="hidden" name={name} value={value} />}
        {required && (
          // Keeps native "required" validation for forms: an empty hidden value blocks submit.
          <input
            tabIndex={-1}
            aria-hidden
            required
            value={value}
            onChange={() => {}}
            className="pointer-events-none absolute inset-0 opacity-0"
          />
        )}
        {open && (
          <Popover>
            <div role="dialog" aria-label={t("pickDate", { label })}>
              <Calendar value={value} onPick={pick} min={min} max={max} />
              <div className="mt-2 flex justify-between border-t border-border pt-2">
                <button
                  type="button"
                  onClick={() => pick(localToday())}
                  disabled={(min ? localToday() < min : false) || (max ? localToday() > max : false)}
                  className="rounded-md px-2 py-1 text-sm font-medium text-accent hover:bg-accent/10 disabled:opacity-40"
                >
                  {tc("today")}
                </button>
                <button type="button" onClick={() => setOpen(false)} className="rounded-md px-2 py-1 text-sm text-muted hover:bg-foreground/5">
                  {tc("close")}
                </button>
              </div>
            </div>
          </Popover>
        )}
      </div>
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </div>
  );
}
