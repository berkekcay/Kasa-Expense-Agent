"use client";

// Building blocks shared by the login, register and Google return pages, and by the Security
// card in Settings: the centred card, the 6-digit code input, the TOTP setup and verify steps,
// and the recovery code list.

import { Check, Copy, Download, Eye, EyeOff, KeyRound, Smartphone } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, type Ref, useEffect, useRef, useState } from "react";
import { LanguageSwitch } from "@/components/Nav";
import { Logo } from "@/components/Logo";
import { Alert, Button, ErrorText, Loading, Spinner, controlClass, errorMessage } from "@/components/ui";
import { ApiError, type AuthStep, type Confirmed, type SignedIn, type TotpSetup, api, saveBlob } from "@/lib/api";
import { signIn } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { messages } from "./messages";

// --- helpers ----------------------------------------------------------------------------------

/** Where to go after signing in: only same-site paths, never back to the auth pages. */
export function safeNext(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return "/";
  try {
    const url = new URL(raw, "http://kasa.local");
    if (url.origin !== "http://kasa.local") return "/";
    if (/^\/(login|register)(\/|$)/.test(url.pathname)) return "/";
    return url.pathname + url.search + url.hash;
  } catch {
    return "/";
  }
}

/** "{privacy} and {terms}" with React nodes in place of the placeholders. */
export function fill(template: string, parts: Record<string, ReactNode>): ReactNode[] {
  return template.split(/\{(\w+)\}/).map((piece, i) => (i % 2 === 1 ? <span key={i}>{parts[piece] ?? piece}</span> : piece));
}

function useCopy(): [(text: string) => Promise<void>, boolean, boolean] {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setFailed(false);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setFailed(true);
    }
  }
  return [copy, copied, failed];
}

/** Focus an element when it mounts (a new step appeared). */
export function useFocusOnMount<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  return ref;
}

// --- layout -----------------------------------------------------------------------------------

/** The centred card the auth pages live in. */
export function AuthShell({
  title,
  subtitle,
  step,
  children,
  footer,
  languageSwitch = true,
}: {
  title: string;
  subtitle?: ReactNode;
  /** "Step 2 of 3" above the title. */
  step?: string;
  children: ReactNode;
  footer?: ReactNode;
  /** Changing the language remounts the app (LocaleRoot), which would lose a pending step. */
  languageSwitch?: boolean;
}) {
  return (
    <div className="relative isolate flex flex-1 flex-col items-center px-4 pt-6 pb-12 sm:pt-10">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[420px] bg-[radial-gradient(60%_100%_at_50%_0%,var(--accent-soft),transparent)]"
      />
      <div className="flex w-full max-w-[440px] items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
          <Logo className="size-9" />
          <span className="text-lg">Kasa</span>
        </Link>
        {languageSwitch && <LanguageSwitch />}
      </div>
      <div className="mt-8 w-full max-w-[440px] sm:mt-12">
        <div className="rounded-2xl border border-border bg-card p-6 shadow-card sm:p-8">
          {step && <p className="mb-2 text-xs font-semibold tracking-wider text-accent uppercase">{step}</p>}
          <h1 className="text-[22px] leading-tight font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-muted">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
        {footer && <p className="mt-6 text-center text-sm text-muted">{footer}</p>}
      </div>
    </div>
  );
}

export const authLinkClass = "font-medium text-accent underline-offset-2 hover:underline";

/** A form-level error box (announced by screen readers). */
export function FormError({ children }: { children: ReactNode }) {
  return (
    <div role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2.5 text-sm text-danger">
      {children}
    </div>
  );
}

/** "or" divider plus "Continue with Google" (a full-page redirect through the API). */
export function GoogleSection({ next }: { next: string }) {
  const t = useT(messages);
  const [opening, setOpening] = useState(false);
  return (
    <>
      <div className="my-5 flex items-center gap-3 text-xs text-muted">
        <span aria-hidden className="h-px flex-1 bg-border" />
        {t("or")}
        <span aria-hidden className="h-px flex-1 bg-border" />
      </div>
      <Button
        variant="ghost"
        className="h-10 w-full"
        disabled={opening}
        onClick={() => {
          setOpening(true);
          window.location.href = api.auth.googleStartUrl(next);
        }}
      >
        {opening ? <Spinner className="size-3.5" /> : <GoogleMark />}
        {opening ? t("openingGoogle") : t("google")}
      </Button>
    </>
  );
}

/** Google's "G", drawn inline (brand colours, so it reads on both themes). */
function GoogleMark() {
  return (
    <svg aria-hidden viewBox="0 0 48 48" className="size-4">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

// --- inputs -----------------------------------------------------------------------------------

export function TextInput({
  id,
  label,
  hint,
  error,
  inputRef,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  id: string;
  label: string;
  hint?: ReactNode;
  error?: boolean;
  inputRef?: Ref<HTMLInputElement>;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1 text-sm">
      <label htmlFor={id} className="text-muted">
        {label}
      </label>
      <input
        id={id}
        ref={inputRef}
        aria-invalid={error || undefined}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className={controlClass}
        {...props}
      />
      {hint && (
        <span id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </span>
      )}
    </div>
  );
}

/** A password input with a show/hide toggle. */
export function PasswordInput({
  id,
  label,
  hint,
  error,
  inputRef,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  id: string;
  label: string;
  hint?: ReactNode;
  error?: boolean;
  inputRef?: Ref<HTMLInputElement>;
}) {
  const t = useT(messages);
  const [shown, setShown] = useState(false);
  return (
    <div className="flex min-w-0 flex-col gap-1 text-sm">
      <label htmlFor={id} className="text-muted">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          ref={inputRef}
          type={shown ? "text" : "password"}
          aria-invalid={error || undefined}
          aria-describedby={hint ? `${id}-hint` : undefined}
          className={`${controlClass} pr-10`}
          {...props}
        />
        <button
          type="button"
          onClick={() => setShown((s) => !s)}
          aria-label={shown ? t("hidePassword") : t("showPassword")}
          aria-pressed={shown}
          aria-controls={id}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-lg text-muted hover:text-foreground"
        >
          {shown ? <EyeOff aria-hidden className="size-4" /> : <Eye aria-hidden className="size-4" />}
        </button>
      </div>
      {hint && (
        <div id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </div>
      )}
    </div>
  );
}

/** One input for a 6-digit TOTP code; calls `onComplete` as soon as six digits are in. */
export function CodeInput({
  id,
  label,
  value,
  onChange,
  onComplete,
  disabled,
  error,
  inputRef,
  autoFocus,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  onComplete?: (code: string) => void;
  disabled?: boolean;
  error?: boolean;
  inputRef?: Ref<HTMLInputElement>;
  autoFocus?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id} className="text-muted">
        {label}
      </label>
      <input
        id={id}
        ref={inputRef}
        name="code"
        value={value}
        onChange={(e) => {
          const digits = e.target.value.replace(/\D/g, "").slice(0, 6);
          onChange(digits);
          if (digits.length === 6 && digits !== value) onComplete?.(digits);
        }}
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]*"
        maxLength={6}
        placeholder="000000"
        disabled={disabled}
        autoFocus={autoFocus}
        aria-invalid={error || undefined}
        className={`${controlClass} h-12 text-center font-mono text-2xl tracking-[0.4em] tabular-nums placeholder:text-muted/40`}
      />
    </div>
  );
}

// --- second step: verify ------------------------------------------------------------------------

/** "Expired, start again" box for a pending token that is older than 10 minutes. */
function Expired({ onRestart }: { onRestart: () => void }) {
  const t = useT(messages);
  return (
    <div className="flex flex-col gap-4">
      <Alert tone="error">{t("expired")}</Alert>
      <Button onClick={onRestart} className="w-full">
        {t("startAgain")}
      </Button>
    </div>
  );
}

function VerifyStep({
  pendingToken,
  onSignedIn,
  onRestart,
  onModeChange,
}: {
  pendingToken: string;
  onSignedIn: (result: SignedIn) => void;
  onRestart: () => void;
  /** Told whether the recovery code input is showing (for the subtitle). */
  onModeChange?: (recovery: boolean) => void;
}) {
  const t = useT(messages);
  const [mode, setMode] = useState<"code" | "recovery">("code");
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const codeRef = useRef<HTMLInputElement>(null);
  const recoveryRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    (mode === "code" ? codeRef : recoveryRef).current?.focus();
  }, [mode]);

  async function submit(value: string) {
    if (busy) return;
    if (mode === "code" && value.length !== 6) return setError(t("errCode"));
    if (mode === "recovery" && !value.trim()) return setError(t("errRecovery"));
    setBusy(true);
    setError(null);
    try {
      const result =
        mode === "code"
          ? await api.auth.verifyCode(pendingToken, value)
          : await api.auth.verifyRecoveryCode(pendingToken, value.trim());
      onSignedIn(result);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setExpired(true);
      else if (err instanceof ApiError && err.status === 400) {
        setError(mode === "code" ? t("wrongCode") : t("wrongRecovery"));
        if (mode === "code") setCode("");
        (mode === "code" ? codeRef : recoveryRef).current?.focus();
      } else setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (expired) return <Expired onRestart={onRestart} />;

  return (
    <form
      noValidate
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        void submit(mode === "code" ? code : recovery);
      }}
      className="flex flex-col gap-4"
    >
      {mode === "code" ? (
        <CodeInput
          id="login-code"
          label={t("code")}
          value={code}
          onChange={setCode}
          onComplete={(c) => void submit(c)}
          disabled={busy}
          error={Boolean(error)}
          inputRef={codeRef}
        />
      ) : (
        <TextInput
          id="login-recovery"
          label={t("recoveryCode")}
          hint={t("recoveryHint")}
          value={recovery}
          onChange={(e) => setRecovery(e.target.value)}
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          disabled={busy}
          error={Boolean(error)}
          inputRef={recoveryRef}
          className={`${controlClass} font-mono`}
        />
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <Button type="submit" disabled={busy} className="h-10 w-full">
        {busy && <Spinner className="size-3.5" />}
        {busy ? t("verifying") : t("verify")}
      </Button>
      <button
        type="button"
        onClick={() => {
          const nextMode = mode === "code" ? "recovery" : "code";
          setMode(nextMode);
          setError(null);
          onModeChange?.(nextMode === "recovery");
        }}
        className="mx-auto inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
      >
        {mode === "code" ? <KeyRound aria-hidden className="size-4" /> : <Smartphone aria-hidden className="size-4" />}
        {mode === "code" ? t("useRecovery") : t("useApp")}
      </button>
    </form>
  );
}

// --- second step: setup -------------------------------------------------------------------------

// One /auth/totp/setup request per pending token, so a double mount (React strict mode in
// development) does not make the server create two secrets and show the stale one.
const setupRequests = new Map<string, Promise<TotpSetup>>();

function loadSetup(pendingToken: string): Promise<TotpSetup> {
  let request = setupRequests.get(pendingToken);
  if (!request) {
    request = api.auth.totpSetup(pendingToken);
    request.catch(() => setupRequests.delete(pendingToken));
    setupRequests.set(pendingToken, request);
  }
  return request;
}

function SetupStep({
  pendingToken,
  onConfirmed,
  onRestart,
}: {
  pendingToken: string;
  onConfirmed: (result: Confirmed) => void;
  onRestart: () => void;
}) {
  const t = useT(messages);
  const [setup, setSetup] = useState<TotpSetup | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [copy, copied, copyFailed] = useCopy();
  const codeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    loadSetup(pendingToken).then(
      (s) => {
        if (!cancelled) setSetup(s);
      },
      (err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) setExpired(true);
        else setLoadError(err);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [pendingToken]);

  useEffect(() => {
    if (setup) codeRef.current?.focus();
  }, [setup]);

  async function confirm(value: string) {
    if (busy) return;
    if (value.length !== 6) return setError(t("errCode"));
    setBusy(true);
    setError(null);
    try {
      onConfirmed(await api.auth.totpConfirm(pendingToken, value));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setExpired(true);
      else {
        setError(err instanceof ApiError && err.status === 400 ? t("wrongCode") : errorMessage(err));
        setCode("");
        codeRef.current?.focus();
      }
      setBusy(false);
    }
  }

  if (expired) return <Expired onRestart={onRestart} />;
  if (loadError) {
    return (
      <div className="flex flex-col gap-4">
        <ErrorText error={errorMessage(loadError)} />
        <Button onClick={onRestart} variant="ghost" className="w-full">
          {t("startAgain")}
        </Button>
      </div>
    );
  }
  if (!setup) return <Loading label={t("preparing")} />;

  const grouped = setup.secret.replace(/\s+/g, "").match(/.{1,4}/g)?.join(" ") ?? setup.secret;

  return (
    <div className="flex flex-col gap-5">
      <ol className="flex flex-col gap-2 text-sm">
        <li className="flex gap-2.5">
          <span aria-hidden className="flex size-5 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
            1
          </span>
          {t("setupStep1")}
        </li>
        <li className="flex gap-2.5">
          <span aria-hidden className="flex size-5 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
            2
          </span>
          {t("setupStep2")}
        </li>
      </ol>
      <div className="flex flex-col items-center gap-3">
        {/* White behind the QR so it scans in dark mode too. */}
        <div className="rounded-xl border border-border bg-white p-3">
          {/* eslint-disable-next-line @next/next/no-img-element -- an inline SVG data URI, nothing to optimise */}
          <img
            src={`data:image/svg+xml;utf8,${encodeURIComponent(setup.qr_svg)}`}
            alt={t("qrAlt")}
            width={176}
            height={176}
            className="size-44"
          />
        </div>
        <a href={setup.otpauth_uri} className="text-sm font-medium text-accent hover:underline sm:hidden">
          {t("openApp")}
        </a>
      </div>
      <div className="rounded-lg bg-foreground/[0.04] p-3 text-sm">
        <p className="text-muted">{t("cantScan")}</p>
        <div className="mt-2 flex items-center justify-between gap-2">
          <code className="font-mono text-[15px] font-semibold tracking-wide break-all">{grouped}</code>
          <Button variant="ghost" size="sm" onClick={() => void copy(setup.secret)} aria-label={t("copyKey")}>
            {copied ? <Check aria-hidden className="size-3.5" /> : <Copy aria-hidden className="size-3.5" />}
            {copied ? t("copied") : t("copy")}
          </Button>
        </div>
        {copyFailed && (
          <p role="alert" className="mt-2 text-xs text-danger">
            {t("copyFailed")}
          </p>
        )}
      </div>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void confirm(code);
        }}
        className="flex flex-col gap-4"
      >
        <CodeInput
          id="setup-code"
          label={t("code")}
          value={code}
          onChange={setCode}
          onComplete={(c) => void confirm(c)}
          disabled={busy}
          error={Boolean(error)}
          inputRef={codeRef}
        />
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <Button type="submit" disabled={busy} className="h-10 w-full">
          {busy && <Spinner className="size-3.5" />}
          {busy ? t("verifying") : t("confirm")}
        </Button>
      </form>
    </div>
  );
}

// --- recovery codes -----------------------------------------------------------------------------

/** The codes in a grid with Copy and Download (.txt). Used after setup and in Settings. */
export function RecoveryCodeList({ codes, email }: { codes: string[]; email?: string | null }) {
  const t = useT(messages);
  const [copy, copied, copyFailed] = useCopy();
  const text = codes.join("\n");

  function download() {
    const lines = [t("fileHeader"), ...(email ? [email] : []), "", ...codes, ""];
    saveBlob(new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" }), "kasa-recovery-codes.txt");
  }

  return (
    <div className="flex flex-col gap-3">
      <ul
        aria-label={t("codesList")}
        className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-border bg-background p-4 font-mono text-[15px] tabular-nums"
      >
        {codes.map((c) => (
          <li key={c} className="text-center select-all">
            {c}
          </li>
        ))}
      </ul>
      <div className="grid grid-cols-2 gap-2">
        <Button variant="ghost" onClick={() => void copy(text)} aria-label={t("copyCodes")}>
          {copied ? <Check aria-hidden className="size-3.5" /> : <Copy aria-hidden className="size-3.5" />}
          {copied ? t("copied") : t("copy")}
        </Button>
        <Button variant="ghost" onClick={download} aria-label={t("downloadCodes")}>
          <Download aria-hidden className="size-3.5" /> {t("download")}
        </Button>
      </div>
      {copyFailed && (
        <p role="alert" className="text-xs text-danger">
          {t("copyFailed")}
        </p>
      )}
    </div>
  );
}

function CodesStep({ result, onDone }: { result: Confirmed; onDone: () => void }) {
  const t = useT(messages);
  const [saved, setSaved] = useState(false);
  const checkRef = useFocusOnMount<HTMLInputElement>();
  return (
    <div className="flex flex-col gap-5">
      <RecoveryCodeList codes={result.recovery_codes} email={result.user.login_email ?? result.user.email} />
      <p className="text-sm text-muted">{t("codesOnce")}</p>
      <label className="flex items-start gap-2.5 text-sm">
        <input
          ref={checkRef}
          type="checkbox"
          checked={saved}
          onChange={(e) => setSaved(e.target.checked)}
          className="mt-0.5 size-4 shrink-0 accent-[var(--accent)]"
        />
        <span>{t("savedThem")}</span>
      </label>
      <Button onClick={onDone} disabled={!saved} className="h-10 w-full">
        {t("goToKasa")}
      </Button>
    </div>
  );
}

// --- the whole second step ----------------------------------------------------------------------

/**
 * Everything after the first step (password, register or Google): verify a code, or set up
 * the authenticator and save recovery codes. There is no way to skip it. On success the
 * session is stored and the browser goes to `next`.
 */
export function TwoFactorFlow({
  pendingToken,
  step,
  next,
  onRestart,
  numbered = false,
}: {
  pendingToken: string;
  step: AuthStep;
  next: string;
  onRestart: () => void;
  /** Show "Step 2 of 3" (the register page). */
  numbered?: boolean;
}) {
  const t = useT(messages);
  const router = useRouter();
  const [confirmed, setConfirmed] = useState<Confirmed | null>(null);
  const [recovery, setRecovery] = useState(false);

  function finish(result: SignedIn) {
    signIn(result.token, result.user, result.expires_at);
    router.replace(next);
  }

  if (confirmed) {
    return (
      <AuthShell languageSwitch={false} title={t("codesTitle")} subtitle={t("codesSubtitle")} step={numbered ? t("stepOf", { n: 3 }) : undefined}>
        <CodesStep result={confirmed} onDone={() => finish(confirmed)} />
      </AuthShell>
    );
  }

  if (step === "totp_setup") {
    return (
      <AuthShell languageSwitch={false} title={t("setupTitle")} subtitle={t("setupSubtitle")} step={numbered ? t("stepOf", { n: 2 }) : undefined}>
        <SetupStep pendingToken={pendingToken} onConfirmed={setConfirmed} onRestart={onRestart} />
      </AuthShell>
    );
  }

  return (
    <AuthShell
      languageSwitch={false}
      title={t("verifyTitle")}
      subtitle={recovery ? t("recoverySubtitle") : t("verifySubtitle")}
      footer={
        <button type="button" onClick={onRestart} className={authLinkClass}>
          {t("back")}
        </button>
      }
    >
      <VerifyStep pendingToken={pendingToken} onSignedIn={finish} onRestart={onRestart} onModeChange={setRecovery} />
    </AuthShell>
  );
}
