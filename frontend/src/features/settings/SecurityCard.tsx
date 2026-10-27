"use client";

// Settings > Security, for Kasa accounts: two-step verification status, new recovery codes,
// password change and the list of signed-in devices.

import { KeyRound, LogOut, Monitor, ShieldCheck, Smartphone } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { useToast } from "@/components/Toast";
import { Alert, Async, Badge, Button, Card, ErrorText, Skeleton, Spinner, errorMessage } from "@/components/ui";
import { CodeInput, PasswordInput, RecoveryCodeList } from "@/features/auth/parts";
import { MIN_PASSWORD, StrengthHint } from "@/features/auth/RegisterView";
import { ApiError, type Me, type SessionInfo, api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { common } from "@/lib/commonMessages";
import { useApi } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { messages } from "./messages";

type T = (key: keyof (typeof messages)["en"] & string, vars?: Record<string, string | number>) => string;

/** One block of the card: label and description on the left, an action on the right, and
 *  optional content (a form, a list) below. */
function Section({
  label,
  description,
  action,
  children,
}: {
  label: string;
  description?: ReactNode;
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
        <div className="min-w-0">
          <h3 className="text-sm font-medium">{label}</h3>
          {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
        </div>
        {action && <div className="flex shrink-0 flex-wrap items-center gap-2 text-sm">{action}</div>}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </section>
  );
}

export function SecurityCard({ me }: { me: Me }) {
  const t = useT(messages);
  const [devicesVersion, setDevicesVersion] = useState(0);
  return (
    <Card id="security" title={t("securityTitle")} description={t("securityDesc")}>
      <div className="flex flex-col divide-y divide-border">
        <Section
          label={t("twoFactor")}
          description={t("twoFactorDesc")}
          action={
            me.totp_enabled === false ? (
              <Badge>{t("twoFactorOff")}</Badge>
            ) : (
              <Badge tone="positive">
                <ShieldCheck aria-hidden className="mr-1 size-3" /> {t("twoFactorOn")}
              </Badge>
            )
          }
        />
        <RecoverySection email={me.login_email ?? me.email} />
        <PasswordSection hasPassword={me.has_password !== false} onChanged={() => setDevicesVersion((v) => v + 1)} />
        <DevicesSection version={devicesVersion} />
      </div>
    </Card>
  );
}

// --- recovery codes ---------------------------------------------------------------------------

function RecoverySection({ email }: { email: string | null | undefined }) {
  const t = useT(messages);
  const tc = useT(common);
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);

  function close() {
    setOpen(false);
    setCode("");
    setError(null);
    setCodes(null);
  }

  async function submit(value: string) {
    if (busy) return;
    if (value.length !== 6) return setError(t("errCode"));
    setBusy(true);
    setError(null);
    try {
      const result = await api.auth.newRecoveryCodes(value);
      setCodes(result.recovery_codes);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 400 ? t("wrongCode") : errorMessage(err));
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section
      label={t("recoveryTitle")}
      description={t("recoveryDesc")}
      action={
        !open && (
          <Button variant="ghost" onClick={() => setOpen(true)}>
            <KeyRound aria-hidden className="size-3.5" /> {t("newCodes")}
          </Button>
        )
      }
    >
      {open &&
        (codes ? (
          <div className="flex max-w-md flex-col gap-3">
            <Alert tone="success">{t("newCodesReady")}</Alert>
            <RecoveryCodeList codes={codes} email={email} />
            <Button variant="ghost" onClick={close} className="self-start">
              {t("done")}
            </Button>
          </div>
        ) : (
          <form
            noValidate
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              void submit(code);
            }}
            className="flex max-w-xs flex-col gap-3"
          >
            <p className="text-sm text-muted">{t("newCodesHint")}</p>
            <CodeInput
              id="recovery-confirm-code"
              label={t("codeLabel")}
              value={code}
              onChange={setCode}
              onComplete={(c) => void submit(c)}
              disabled={busy}
              error={Boolean(error)}
              autoFocus
            />
            <ErrorText error={error} />
            <div className="flex gap-2">
              <Button type="submit" disabled={busy}>
                {busy && <Spinner className="size-3.5" />}
                {t("makeCodes")}
              </Button>
              <Button variant="ghost" onClick={close}>
                {tc("cancel")}
              </Button>
            </div>
          </form>
        ))}
    </Section>
  );
}

// --- password ---------------------------------------------------------------------------------

function PasswordSection({ hasPassword, onChanged }: { hasPassword: boolean; onChanged: () => void }) {
  const t = useT(messages);
  const tc = useT(common);
  const notify = useToast();
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState({ current: "", next: "", code: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    setOpen(false);
    setValues({ current: "", next: "", code: "" });
    setError(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!values.current) return setError(t("errCurrentPassword"));
    if (values.next.length < MIN_PASSWORD) return setError(t("errPasswordShort"));
    if (values.code.length !== 6) return setError(t("errCode"));
    setBusy(true);
    setError(null);
    try {
      await api.auth.changePassword(values.current, values.next, values.code);
      notify(t("passwordChanged"), "success");
      close();
      onChanged();
    } catch (err) {
      // The server's own words (wrong current password, wrong code, weak password).
      setError(err instanceof ApiError && err.status !== 0 ? err.message : errorMessage(err));
      setValues((v) => ({ ...v, code: "" }));
    } finally {
      setBusy(false);
    }
  }

  if (!hasPassword) return <Section label={t("passwordTitle")} description={t("passwordGoogle")} />;

  return (
    <Section
      label={t("passwordTitle")}
      description={t("passwordDesc")}
      action={
        !open && (
          <Button variant="ghost" onClick={() => setOpen(true)}>
            {t("changePassword")}
          </Button>
        )
      }
    >
      {open && (
        <form noValidate onSubmit={onSubmit} className="flex max-w-sm flex-col gap-3">
          <PasswordInput
            id="settings-current-password"
            label={t("currentPassword")}
            autoComplete="current-password"
            value={values.current}
            onChange={(e) => setValues((v) => ({ ...v, current: e.target.value }))}
            autoFocus
          />
          <PasswordInput
            id="settings-new-password"
            label={t("newPassword")}
            autoComplete="new-password"
            minLength={MIN_PASSWORD}
            value={values.next}
            onChange={(e) => setValues((v) => ({ ...v, next: e.target.value }))}
            hint={<StrengthHint password={values.next} />}
          />
          <CodeInput
            id="settings-password-code"
            label={t("codeLabel")}
            value={values.code}
            onChange={(code) => setValues((v) => ({ ...v, code }))}
            disabled={busy}
          />
          <ErrorText error={error} />
          <div className="flex gap-2">
            <Button type="submit" disabled={busy}>
              {busy && <Spinner className="size-3.5" />}
              {t("changePassword")}
            </Button>
            <Button variant="ghost" onClick={close}>
              {tc("cancel")}
            </Button>
          </div>
        </form>
      )}
    </Section>
  );
}

// --- devices ----------------------------------------------------------------------------------

const BROWSERS: [RegExp, string][] = [
  [/Edg(e|A|iOS)?\//, "Edge"],
  [/OPR\/|Opera/, "Opera"],
  [/SamsungBrowser/, "Samsung Internet"],
  [/Firefox\/|FxiOS/, "Firefox"],
  [/CriOS|Chrome\//, "Chrome"],
  [/Safari\//, "Safari"],
];
const SYSTEMS: [RegExp, string][] = [
  [/iPhone/, "iPhone"],
  [/iPad/, "iPad"],
  [/Android/, "Android"],
  [/Windows/, "Windows"],
  [/CrOS/, "ChromeOS"],
  [/Mac OS X|Macintosh/, "macOS"],
  [/Linux/, "Linux"],
];

/** "Chrome on Windows" from a user agent string, plus whether it looks like a phone. */
export function describeDevice(ua: string | null, t: T): { label: string; mobile: boolean } {
  if (!ua) return { label: t("unknownDevice"), mobile: false };
  const browser = BROWSERS.find(([re]) => re.test(ua))?.[1];
  const os = SYSTEMS.find(([re]) => re.test(ua))?.[1];
  const mobile = /Mobile|iPhone|Android/.test(ua);
  if (browser && os) return { label: t("deviceOn", { browser, os }), mobile };
  const label = browser ?? os ?? (ua.length > 40 ? `${ua.slice(0, 40)}...` : ua);
  return { label, mobile };
}

function DevicesSection({ version }: { version: number }) {
  const t = useT(messages);
  const notify = useToast();
  const sessions = useApi(() => api.auth.sessions(), [version]);
  const [busy, setBusy] = useState<string | null>(null);

  async function revoke(ids: string[], done: string) {
    setBusy(ids.length === 1 ? ids[0] : "others");
    try {
      for (const id of ids) await api.auth.revokeSession(id);
      notify(done, "success");
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(null);
      sessions.reload();
    }
  }

  const others = (sessions.data ?? []).filter((s) => !s.current);

  return (
    <Section
      label={t("devicesTitle")}
      description={t("devicesDesc")}
      action={
        others.length > 0 && (
          <Button
            variant="ghost"
            disabled={busy !== null}
            onClick={() =>
              void revoke(
                others.map((s) => s.id),
                t("othersSignedOut"),
              )
            }
          >
            {busy === "others" ? <Spinner className="size-3.5" /> : <LogOut aria-hidden className="size-3.5" />}
            {t("signOutOthers")}
          </Button>
        )
      }
    >
      <Async {...sessions} label={t("devicesLoading")} fallback={<Skeleton className="h-16 w-full" />}>
        {(list: SessionInfo[]) => (
          <ul className="flex flex-col gap-2">
            {[...list]
              .sort((a, b) => Number(b.current) - Number(a.current))
              .map((s) => {
                const device = describeDevice(s.user_agent, t);
                const Icon = device.mobile ? Smartphone : Monitor;
                return (
                  <li key={s.id} className="flex items-center gap-3 rounded-lg border border-border px-3 py-2.5">
                    <span
                      aria-hidden
                      className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-foreground/[0.05] text-foreground/70"
                    >
                      <Icon className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium" title={s.user_agent ?? undefined}>
                        {device.label}
                      </span>
                      <span className="block truncate text-xs text-muted">
                        {s.last_seen_at
                          ? t("lastSeen", { date: formatDateTime(s.last_seen_at) })
                          : t("signedInAt", { date: formatDateTime(s.created_at) })}
                      </span>
                    </span>
                    {s.current ? (
                      <Badge tone="accent">{t("thisDevice")}</Badge>
                    ) : (
                      <Button
                        variant="subtle"
                        size="sm"
                        disabled={busy !== null}
                        aria-label={t("revokeLabel", { device: device.label })}
                        onClick={() => void revoke([s.id], t("revoked"))}
                      >
                        {busy === s.id && <Spinner className="size-3" />}
                        {t("revoke")}
                      </Button>
                    )}
                  </li>
                );
              })}
            {others.length === 0 && <li className="px-1 text-sm text-muted">{t("noOtherDevices")}</li>}
          </ul>
        )}
      </Async>
    </Section>
  );
}
