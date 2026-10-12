// Small styling primitives shared by every page.
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { formatMoney } from "@/lib/format";

export { errorMessage } from "@/lib/errors";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </header>
  );
}

export function Card({
  title,
  actions,
  children,
  className = "",
  id,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={`min-w-0 rounded-xl border border-border bg-card p-4 sm:p-5 ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

type Variant = "primary" | "ghost" | "danger" | "subtle";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-foreground hover:opacity-90",
  ghost: "border border-border hover:bg-foreground/5",
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
  "h-9 w-full min-w-0 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/30 aria-[invalid=true]:border-danger";

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
const TONES: Record<Tone, { box: string; icon: string; label: string }> = {
  info: { box: "border-border bg-foreground/[0.03]", icon: "i", label: "Note" },
  success: { box: "border-positive/40 bg-positive/10", icon: "✓", label: "Done" },
  warning: { box: "border-[var(--status-warning)]/60 bg-[var(--status-warning)]/10", icon: "!", label: "Warning" },
  error: { box: "border-danger/40 bg-danger/10", icon: "×", label: "Error" },
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
        <span className="sr-only">{t.label}: </span>
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={title ? "mt-0.5" : ""}>{children}</div>}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
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

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-muted">
      <Spinner /> {label}
    </p>
  );
}

export function Empty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 text-sm text-muted">
      <p>{children}</p>
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
}: {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload?: () => void;
  label?: string;
  children: (data: T) => ReactNode;
}) {
  if (error && data === null) {
    return (
      <div className="flex flex-col items-start gap-2">
        <ErrorText error={error} />
        {reload && (
          <Button variant="ghost" size="sm" onClick={reload}>
            Try again
          </Button>
        )}
      </div>
    );
  }
  if (data === null) return <Loading label={label} />;
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
