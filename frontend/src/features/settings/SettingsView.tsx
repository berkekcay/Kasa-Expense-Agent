"use client";

import { CalendarPlus, Check, Inbox, MailSearch, MailX, RefreshCw, ShieldCheck, Unplug, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, type ReactNode, useState } from "react";
import { api, type GoogleStatus, type SyncResult } from "@/lib/api";
import { firebaseEnabled } from "@/lib/auth";
import { common } from "@/lib/commonMessages";
import { formatDateTime } from "@/lib/format";
import { dataChanged, useApi, useMe } from "@/lib/hooks";
import { LOCALES, type Locale, setLocale, useLocale, useT } from "@/lib/i18n";
import { useAuthUser, useSession, useUserId } from "@/lib/user";
import { AccountMenu, DevUserSwitcher, SignOutButton } from "@/components/Nav";
import { useToast } from "@/components/Toast";
import {
  Alert,
  Async,
  Badge,
  Button,
  Card,
  ErrorText,
  Field,
  PageHeader,
  Segmented,
  Skeleton,
  Spinner,
  errorMessage,
} from "@/components/ui";
import { messages } from "./messages";
import { SecurityCard } from "./SecurityCard";

const OAUTH_REASONS = ["denied", "scopes", "invalid", "not_configured", "google"] as const;

/** The page header, translated on the client (the page itself is a server component). */
export function SettingsHeader() {
  const t = useT(messages);
  return <PageHeader title={t("title")} subtitle={t("subtitle")} />;
}

export function SettingsView() {
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <OAuthReturn />
      <ProfileCard />
      <AccountCard />
      <SecuritySection />
      <GoogleCard />
      <DataCard />
    </div>
  );
}

/** One settings line: what it is on the left, its value or control on the right. */
function Row({ label, description, children }: { label: string; description?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
      <div className="min-w-0">
        <p className="text-sm font-medium">{label}</p>
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      {children && <div className="flex min-w-0 shrink-0 flex-wrap items-center gap-2 text-sm sm:justify-end">{children}</div>}
    </div>
  );
}

function Rows({ children }: { children: ReactNode }) {
  return <div className="flex flex-col divide-y divide-border">{children}</div>;
}

/** Message for the ?google=connected|error&reason=... redirect back from the OAuth callback. */
function OAuthReturn() {
  const t = useT(messages);
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const result = params.get("google");
  if (!result) return null;
  const clear = () => router.replace(pathname, { scroll: false });
  const raw = params.get("reason") ?? "google";
  const reason = (OAUTH_REASONS as readonly string[]).includes(raw) ? (raw as (typeof OAUTH_REASONS)[number]) : "google";
  return result === "connected" ? (
    <Alert tone="success" title={t("connectedTitle")} onDismiss={clear}>
      {t("connectedText")}
    </Alert>
  ) : (
    <Alert tone="error" title={t("notConnectedTitle")} onDismiss={clear}>
      {t(`oauth.${reason}`)}
    </Alert>
  );
}

// --- Profile ----------------------------------------------------------------------------------

function ProfileCard() {
  const me = useMe();
  const notify = useToast();
  const t = useT(messages);
  const tc = useT(common);
  const locale = useLocale();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const name = String(new FormData(e.currentTarget).get("display_name") ?? "").trim();
    if (!name) {
      setError(t("errName"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const saved = await api.me.setDisplayName(name);
      notify(t("nameSaved", { name: saved.display_name }), "success");
      dataChanged("profile");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title={t("profileTitle")} description={t("profileDesc")}>
      <Async {...me} label={t("profileLoading")} fallback={<Skeleton className="h-16 w-full max-w-md" />}>
        {(profile) => (
          <form key={profile.display_name} onSubmit={onSubmit} className="flex flex-col gap-2">
            <div className="flex flex-wrap items-end gap-3">
              <Field
                label={t("displayName")}
                name="display_name"
                required
                maxLength={100}
                defaultValue={profile.display_name}
                autoComplete="name"
                className="min-w-48 flex-1 sm:max-w-sm"
              />
              <Button type="submit" variant="ghost" disabled={saving}>
                {saving && <Spinner className="size-3.5" />}
                {saving ? tc("saving") : t("saveName")}
              </Button>
            </div>
            <ErrorText error={error} />
          </form>
        )}
      </Async>
      <div className="mt-5 border-t border-border pt-4">
        <Row label={t("language")} description={t("languageDesc")}>
          <Segmented<Locale> label={t("language")} value={locale} options={LOCALES} onChange={setLocale} />
        </Row>
      </div>
    </Card>
  );
}

// --- Account ----------------------------------------------------------------------------------

function AccountCard() {
  const health = useApi(() => api.health(), []);
  const user = useAuthUser();
  const userId = useUserId();
  const session = useSession();
  const me = useMe();
  const t = useT(messages);
  // Split around the id so it can be bold in either word order.
  const [beforeId, afterId] = t("devUserDesc", { id: "\u0000" }).split("\u0000");
  const serverAuth = health.data?.auth;
  const accountName = me.data?.display_name || session?.user?.display_name || "";
  const loginEmail = me.data?.login_email ?? me.data?.email ?? session?.user?.login_email ?? session?.user?.email;

  return (
    <Card
      title={t("accountTitle")}
      description={session ? t("accountDescSession") : firebaseEnabled ? t("accountDescFirebase") : t("accountDescDev")}
    >
      <Rows>
        {session ? (
          <Row label={t("signedInAs")} description={loginEmail ? `${accountName} (${loginEmail})` : accountName}>
            <SignOutButton />
          </Row>
        ) : firebaseEnabled ? (
          <Row label={t("signedInAs")} description={user ? (user.displayName ?? user.email) : t("notSignedIn")}>
            <AccountMenu />
          </Row>
        ) : serverAuth === "accounts" ? null : (
          <Row
            label={t("devUser")}
            description={
              <>
                {beforeId}
                <span className="font-medium text-foreground">{userId}</span>
                {afterId}
              </>
            }
          >
            <DevUserSwitcher idPrefix="settings-dev-user" />
          </Row>
        )}
        {health.data && (
          <>
            <Row label={t("serverSignIn")} description={t("serverSignInDesc")}>
              <span className="text-muted sm:text-right">
                {serverAuth === "firebase" ? t("firebase") : serverAuth === "accounts" ? t("accounts") : t("devHeader")}
              </span>
            </Row>
            <Row label={t("aiModel")} description={t("aiModelDesc")}>
              <span className="inline-flex items-center gap-2 text-muted">
                <span
                  aria-hidden
                  className={`size-2 rounded-full ${health.data.agents_enabled ? "bg-[var(--status-good)]" : "bg-[var(--status-warning)]"}`}
                />
                {health.data.agents_enabled ? t("aiOn", { provider: health.data.llm_provider ?? "" }) : t("aiOff")}
              </span>
            </Row>
          </>
        )}
      </Rows>
      <ErrorText error={health.error} />
    </Card>
  );
}

/** The Security card, only for a Kasa account session (GET /me says kind "account"). */
function SecuritySection() {
  const me = useMe();
  const session = useSession();
  if (!session || me.data?.kind !== "account") return null;
  return <SecurityCard me={me.data} />;
}

// --- Google -----------------------------------------------------------------------------------

function Access({ ok }: { ok: boolean }) {
  const t = useT(messages);
  return ok ? (
    <Badge tone="positive">
      <Check aria-hidden className="mr-1 size-3" /> {t("allowed")}
    </Badge>
  ) : (
    <Badge>
      <X aria-hidden className="mr-1 size-3" /> {t("notAllowed")}
    </Badge>
  );
}

function GoogleCard() {
  const status = useApi(() => api.integrations.googleStatus(), []);
  const notify = useToast();
  const t = useT(messages);
  const [busy, setBusy] = useState<"connect" | "sync" | "disconnect" | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [sync, setSync] = useState<SyncResult | null>(null);

  async function connect() {
    setBusy("connect");
    try {
      const { url } = await api.integrations.googleConnectUrl();
      window.location.assign(url);
    } catch (err) {
      notify(errorMessage(err), "error");
      setBusy(null);
    }
  }

  async function syncNow() {
    setBusy("sync");
    setSync(null);
    try {
      setSync(await api.integrations.googleSync());
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function disconnect() {
    setBusy("disconnect");
    try {
      await api.integrations.googleDisconnect();
      notify(t("disconnectedToast"), "success");
      setConfirm(false);
      setSync(null);
      status.reload();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card title={t("googleTitle")} description={t("googleDesc")}>
      <Async {...status} label={t("googleLoading")} fallback={<Skeleton className="h-24 w-full" />}>
        {(s: GoogleStatus) =>
          !s.configured && !s.connected ? (
            <Alert tone="info" title={t("notAvailableTitle")}>
              {t("notAvailableText")}
            </Alert>
          ) : (
            <div className="flex flex-col gap-4 text-sm">
              <Rows>
                <Row label={t("status")} description={s.google_email ?? (s.connected ? undefined : t("noAccount"))}>
                  {s.connected ? <Badge tone="positive">{t("connected")}</Badge> : <Badge>{t("notConnected")}</Badge>}
                </Row>
                {s.connected && (
                  <>
                    <Row label={t("gmail")} description={t("gmailDesc")}>
                      <Access ok={s.gmail_access} />
                    </Row>
                    <Row label={t("calendar")} description={t("calendarDesc")}>
                      <Access ok={s.calendar_access} />
                    </Row>
                    <Row label={t("newEmail")}>
                      <span className="text-muted sm:text-right">
                        {s.gmail_watch_expires_at
                          ? t("watchUntil", { date: formatDateTime(s.gmail_watch_expires_at) })
                          : t("hourly")}
                      </span>
                    </Row>
                  </>
                )}
              </Rows>
              {s.connected && (!s.gmail_access || !s.calendar_access) && <Alert tone="warning">{t("missingAccess")}</Alert>}
              <div className="flex flex-wrap gap-2 border-t border-border pt-4">
                {(!s.connected || !s.gmail_access || !s.calendar_access) && (
                  <Button onClick={connect} disabled={busy !== null || !s.configured}>
                    {busy === "connect" ? t("openingGoogle") : s.connected ? t("connectAgain") : t("connectGoogle")}
                  </Button>
                )}
                {s.connected && s.gmail_access && (
                  <Button variant="ghost" onClick={syncNow} disabled={busy !== null}>
                    {busy === "sync" ? <Spinner className="size-3.5" /> : <RefreshCw aria-hidden className="size-3.5" />}
                    {busy === "sync" ? t("checkingEmail") : t("checkEmailNow")}
                  </Button>
                )}
                {s.connected &&
                  (confirm ? (
                    <span className="flex flex-wrap items-center gap-2 sm:ml-auto">
                      <span className="text-muted">{t("confirmDisconnect")}</span>
                      <Button variant="danger" onClick={disconnect} disabled={busy !== null}>
                        {t("disconnectGoogle")}
                      </Button>
                      <Button variant="ghost" onClick={() => setConfirm(false)}>
                        {t("keepConnected")}
                      </Button>
                    </span>
                  ) : (
                    <Button variant="subtle" className="sm:ml-auto" onClick={() => setConfirm(true)} disabled={busy !== null}>
                      <Unplug aria-hidden className="size-3.5" /> {t("disconnect")}
                    </Button>
                  ))}
              </div>
              <div aria-live="polite">
                {busy === "sync" && <p className="text-muted">{t("syncSlow")}</p>}
                {sync && (
                  <Alert tone={sync.error ? "warning" : "success"} title={t("syncDone")} onDismiss={() => setSync(null)}>
                    {t("syncSummary", {
                      fetched: sync.fetched,
                      created: sync.created,
                      ignored: sync.ignored,
                      duplicates: sync.duplicates,
                    })}
                    {sync.failed > 0 && t("syncFailed", { n: sync.failed })}.
                    {sync.error && <span className="mt-1 block">{sync.error}</span>}
                  </Alert>
                )}
              </div>
            </div>
          )
        }
      </Async>
    </Card>
  );
}

// --- Data -------------------------------------------------------------------------------------

const DATA_POINTS = [
  { icon: MailSearch, key: "data1" },
  { icon: MailX, key: "data2" },
  { icon: Inbox, key: "data3" },
  { icon: ShieldCheck, key: "data4" },
  { icon: CalendarPlus, key: "data5" },
  { icon: Unplug, key: "data6" },
] as const;

function DataCard() {
  const t = useT(messages);
  return (
    <Card title={t("dataTitle")} description={t("dataDesc")}>
      <ul className="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
        {DATA_POINTS.map(({ icon: Icon, key }) => (
          <li key={key} className="flex items-start gap-3">
            <span aria-hidden className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-foreground/[0.05] text-foreground/70">
              <Icon className="size-4" />
            </span>
            <span className="pt-1.5 text-muted">{t(key)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
