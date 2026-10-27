"use client";

// Small styling primitives shared by every page.
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { common } from "@/lib/commonMessages";
import { formatMoney } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { uiMessages } from "./messages";

export { errorMessage } from "@/lib/errors";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4 sm:mb-8">
      <div className="min-w-0">
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Card({
  title,
  description,
  actions,
  children,
  className = "",
  id,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={`min-w-0 rounded-2xl border border-border bg-card p-5 shadow-card sm:p-6 ${className}`}>
      {(title || actions) && (
        <div className="mb-5 flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>}
            {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

/** A link styled as a quiet card action ("See all"). */
export const cardLinkClass =
  "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-sm font-medium text-accent hover:bg-accent/10";

type Variant = "primary" | "ghost" | "danger" | "subtle";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-foreground shadow-card hover:brightness-110 active:brightness-95",
  ghost: "border border-border bg-card shadow-card hover:border-border-strong hover:bg-card-hover",
  danger: "border border-danger/40 text-danger hover:bg-danger/10",
  subtle: "text-accent hover:bg-accent/10",
};

export function Button({
  className = "",
  variant = "primary",
  size = "md",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" }) {
  const sizing = size === "sm" ? "h-8 px-3 text-xs" : "h-9 px-4 text-sm";
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium whitespace-nowrap transition disabled:cursor-not-allowed disabled:opacity-50 ${sizing} ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

const CONTROL =
  "h-9 w-full min-w-0 rounded-lg border border-border bg-background px-3 text-sm outline-none transition hover:border-border-strong focus:border-accent focus:ring-2 focus:ring-accent/30 aria-[invalid=true]:border-danger";

export function Field({
  label,
  hint,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return (
    <label className={`flex min-w-0 flex-col gap-1 text-sm ${className}`}>
      <span className="text-muted">{label}</span>
      <input className={CONTROL} {...props} />
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </label>
  );
}

export function SelectField({
  label,
  className = "",
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return (
    <label className={`flex min-w-0 flex-col gap-1 text-sm ${className}`}>
      <span className="text-muted">{label}</span>
      <select className={`${CONTROL} px-2`} {...props}>
        {children}
      </select>
    </label>
  );
}

export function TextArea({
  label,
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  return (
    <label className={`flex min-w-0 flex-col gap-1 text-sm ${className}`}>
      <span className="text-muted">{label}</span>
      <textarea className={`${CONTROL} h-auto min-h-16 py-2`} {...props} />
    </label>
  );
}

/** Bare input/select classes for inline (table-like) editing with a separate label. */
export const controlClass = CONTROL;

type Tone = "info" | "success" | "warning" | "error";
const TONES: Record<Tone, { box: string; icon: string }> = {
  info: { box: "border-border bg-foreground/[0.03]", icon: "i" },
  success: { box: "border-positive/40 bg-positive/10", icon: "✓" },
  warning: { box: "border-[var(--status-warning)]/60 bg-[var(--status-warning)]/10", icon: "!" },
  error: { box: "border-danger/40 bg-danger/10", icon: "×" },
};

export function Alert({
  tone = "info",
  title,
  children,
  onDismiss,
  className = "",
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
  onDismiss?: () => void;
  className?: string;
}) {
  const t = TONES[tone];
  const tr = useT(uiMessages);
  const tc = useT(common);
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex gap-3 rounded-lg border px-3 py-2.5 text-sm ${t.box} ${className}`}
    >
      <span
        aria-hidden
        className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border border-current text-xs font-bold"
      >
        {t.icon}
      </span>
      <div className="min-w-0 flex-1">
        <span className="sr-only">{tr(`tone.${tone}`)}: </span>
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={title ? "mt-0.5" : ""}>{children}</div>}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label={tc("dismiss")}
          className="-mr-1 h-6 w-6 shrink-0 rounded text-muted hover:text-foreground"
        >
          ×
        </button>
      )}
    </div>
  );
}

export function ErrorText({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <p role="alert" className="mt-3 text-sm text-danger">
      {error}
    </p>
  );
}

/** Formatted money. `amount` is the API's decimal string. */
export function Money({
  amount,
  currency,
  className = "",
  signed = false,
}: {
  amount: string;
  currency: string;
  className?: string;
  signed?: boolean;
}) {
  const plus = signed && !amount.startsWith("-") && !/^0+(\.0+)?$/.test(amount) ? "+" : "";
  return <span className={`whitespace-nowrap ${className}`}>{plus + formatMoney(amount, currency)}</span>;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "accent" | "warning" | "danger" | "positive" }) {
  const styles = {
    neutral: "border-border text-muted",
    accent: "border-accent/30 bg-accent/10 text-accent",
    warning: "border-[var(--status-warning)]/60 bg-[var(--status-warning)]/10 text-warning",
    danger: "border-danger/30 bg-danger/10 text-danger",
    positive: "border-positive/30 bg-positive/10 text-positive",
  }[tone];
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap ${styles}`}>
      {children}
    </span>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent motion-reduce:animate-none ${className}`}
    />
  );
}

/** Grey placeholder blocks while data loads, in the shape of what will appear. */
export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <span aria-hidden className={`skeleton block rounded-md ${className}`} />;
}

/** Pill-shaped single choice, for view switches ("Month / Year", "Bar / Line"). */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg bg-foreground/[0.05] p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={`h-7 rounded-md px-2.5 text-xs font-medium whitespace-nowrap transition ${value === o.value ? "bg-card text-foreground shadow-card" : "text-muted hover:text-foreground"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Loading({ label }: { label?: string }) {
  const t = useT(common);
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-muted">
      <Spinner /> {label ?? t("loading")}
    </p>
  );
}

export function Empty({ children, action, icon }: { children: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted">
      {icon && (
        <span
          aria-hidden
          className="flex size-10 items-center justify-center rounded-full bg-foreground/[0.05] text-foreground/60 [&>svg]:size-5"
        >
          {icon}
        </span>
      )}
      <p className="max-w-sm">{children}</p>
      {action}
    </div>
  );
}

/** Loading / error / content switch for one API resource. */
export function Async<T>({
  data,
  error,
  loading,
  reload,
  children,
  label,
  fallback,
}: {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload?: () => void;
  label?: string;
  /** Shown instead of the spinner on the first load, e.g. skeleton blocks. */
  fallback?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  const t = useT(common);
  if (error && data === null) {
    return (
      <div className="flex flex-col items-start gap-2">
        <ErrorText error={error} />
        {reload && (
          <Button variant="ghost" size="sm" onClick={reload}>
            {t("tryAgain")}
          </Button>
        )}
      </div>
    );
  }
  if (data === null) {
    if (!fallback) return <Loading label={label} />;
    return (
      <div role="status" aria-label={label ?? t("loading")}>
        {fallback}
      </div>
    );
  }
  return (
    <div className={`transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
      {error && <ErrorText error={error} />}
      {children(data)}
    </div>
  );
}

/** A labelled number tile. Big values use proportional figures. */
export function Stat({ label, value, detail }: { label: string; value: ReactNode; detail?: ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {detail && <div className="mt-1 text-sm text-muted">{detail}</div>}
    </div>
  );
}

/** A KPI card: icon, label, value, and an optional footer (delta, link or sparkline). */
export function StatCard({
  icon,
  label,
  value,
  footer,
  className = "",
}: {
  icon?: ReactNode;
  label: string;
  value: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex min-w-0 flex-col rounded-2xl border border-border bg-card p-5 shadow-card ${className}`}>
      <div className="flex items-center gap-2 text-sm text-muted">
        {icon && (
          <span
            aria-hidden
            className="flex size-7 items-center justify-center rounded-lg bg-foreground/[0.05] text-foreground/70 [&>svg]:size-4"
          >
            {icon}
          </span>
        )}
        {label}
      </div>
      <div className="mt-3 truncate text-2xl font-semibold tracking-tight">{value}</div>
      {footer && <div className="mt-auto pt-2 text-sm text-muted">{footer}</div>}
    </div>
  );
}
