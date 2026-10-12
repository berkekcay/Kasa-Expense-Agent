"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { api, type GoogleStatus, type SyncResult } from "@/lib/api";
import { firebaseEnabled } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { useAuthUser, useUserId } from "@/lib/user";
import { AccountMenu, DevUserSwitcher } from "@/components/Nav";
import { useToast } from "@/components/Toast";
import { Alert, Async, Badge, Button, Card, Spinner, errorMessage } from "@/components/ui";

const OAUTH_ERRORS: Record<string, string> = {
  denied: "You cancelled the Google sign-in, so nothing was connected.",
  scopes: "Google did not grant the access Kasa needs. Try again and tick both Gmail and Calendar.",
  invalid: "The sign-in link expired or was not valid. Start again from this page.",
  not_configured: "Google connection is not set up on the server yet.",
  google: "Google returned an error. Try again in a minute.",
};

export function SettingsView() {
  return (
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <OAuthReturn />
      <GoogleCard />
      <div className="flex flex-col gap-6">
        <AccountCard />
        <GmailExplainer />
      </div>
    </div>
  );
}

/** Message for the ?google=connected|error&reason=... redirect back from the OAuth callback. */
function OAuthReturn() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const result = params.get("google");
  if (!result) return null;
  const clear = () => router.replace(pathname, { scroll: false });
  const reason = params.get("reason") ?? "google";
  return (
    <div className="lg:col-span-2">
      {result === "connected" ? (
        <Alert tone="success" title="Google is connected" onDismiss={clear}>
          Kasa will check your Gmail for receipts and can add settle-up reminders to your calendar.
        </Alert>
      ) : (
        <Alert tone="error" title="Google was not connected" onDismiss={clear}>
          {OAUTH_ERRORS[reason] ?? OAUTH_ERRORS.google}
        </Alert>
      )}
    </div>
  );
}

function Access({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <span>{label}</span>
      {ok ? <Badge tone="positive">✓ Allowed</Badge> : <Badge>Not allowed</Badge>}
    </li>
  );
}

function GoogleCard() {
  const status = useApi(() => api.integrations.googleStatus(), []);
  const notify = useToast();
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
      notify("Google is disconnected. Kasa no longer reads your Gmail.", "success");
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
    <Card title="Google account">
      <Async {...status} label="Checking the Google connection">
        {(s: GoogleStatus) =>
          !s.configured && !s.connected ? (
            <Alert tone="info" title="Not available on this server">
              The server has no Google sign-in set up, so Gmail import and Calendar reminders are off. You can still import
              statements and add expenses by hand.
            </Alert>
          ) : (
            <div className="flex flex-col gap-4 text-sm">
              <p className="flex flex-wrap items-center gap-2">
                {s.connected ? <Badge tone="positive">Connected</Badge> : <Badge>Not connected</Badge>}
                {s.google_email && <span className="font-medium">{s.google_email}</span>}
              </p>
              {s.connected && (
                <ul className="flex flex-col divide-y divide-border">
                  <Access ok={s.gmail_access} label="Read Gmail (receipts and invoices)" />
                  <Access ok={s.calendar_access} label="Add Calendar events (reminders)" />
                  <li className="flex items-center justify-between gap-3 py-2">
                    <span>New email</span>
                    <span className="text-right text-muted">
                      {s.gmail_watch_expires_at
                        ? `Checked right away until ${formatDateTime(s.gmail_watch_expires_at)}`
                        : "Checked every hour"}
                    </span>
                  </li>
                </ul>
              )}
              {s.connected && (!s.gmail_access || !s.calendar_access) && (
                <Alert tone="warning">Some access is missing. Connect again and allow both to use every feature.</Alert>
              )}
              <div className="flex flex-wrap gap-2">
                {(!s.connected || !s.gmail_access || !s.calendar_access) && (
                  <Button onClick={connect} disabled={busy !== null || !s.configured}>
                    {busy === "connect" ? "Opening Google" : s.connected ? "Connect again" : "Connect Google"}
                  </Button>
                )}
                {s.connected && s.gmail_access && (
                  <Button variant="ghost" onClick={syncNow} disabled={busy !== null}>
                    {busy === "sync" ? (
                      <>
                        <Spinner /> Checking email
                      </>
                    ) : (
                      "Check email now"
                    )}
                  </Button>
                )}
                {s.connected &&
                  (confirm ? (
                    <>
                      <Button variant="danger" onClick={disconnect} disabled={busy !== null}>
                        Disconnect Google
                      </Button>
                      <Button variant="ghost" onClick={() => setConfirm(false)}>
                        Keep connected
                      </Button>
                    </>
                  ) : (
                    <Button variant="subtle" onClick={() => setConfirm(true)} disabled={busy !== null}>
                      Disconnect
                    </Button>
                  ))}
              </div>
              <div aria-live="polite">
                {busy === "sync" && (
                  <p className="text-muted">Each new email is read by the AI model, so this can take a few minutes.</p>
                )}
                {sync && (
                  <Alert tone={sync.error ? "warning" : "success"} title="Email check finished" onDismiss={() => setSync(null)}>
                    {sync.fetched} emails looked at, {sync.created} new in your inbox, {sync.ignored} not expenses,{" "}
                    {sync.duplicates} already seen
                    {sync.failed > 0 && `, ${sync.failed} could not be read`}.
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

function AccountCard() {
  const health = useApi(() => api.health(), []);
  const user = useAuthUser();
  const userId = useUserId();

  return (
    <Card title="Signed in as">
      <div className="flex flex-col gap-4 text-sm">
        {firebaseEnabled ? (
          <>
            <p>{user ? <span className="font-medium">{user.displayName ?? user.email}</span> : "You are not signed in."}</p>
            <AccountMenu />
          </>
        ) : (
          <>
            <p>
              Dev mode: you act as <span className="font-medium">{userId}</span>. Switch to another id to test sharing a house.
            </p>
            <DevUserSwitcher idPrefix="settings-dev-user" />
          </>
        )}
        {health.data && (
          <ul className="flex flex-col divide-y divide-border text-muted">
            <li className="flex justify-between gap-3 py-1.5">
              <span>Server sign-in</span>
              <span>{health.data.auth === "firebase" ? "Firebase" : "Dev header"}</span>
            </li>
            <li className="flex justify-between gap-3 py-1.5">
              <span>AI model</span>
              <span>{health.data.agents_enabled ? `On (${health.data.llm_provider})` : "Off"}</span>
            </li>
          </ul>
        )}
        {health.error && <p className="text-danger">{health.error}</p>}
      </div>
    </Card>
  );
}

function GmailExplainer() {
  return (
    <Card title="What Kasa reads from Gmail">
      <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm text-muted">
        <li>Only emails from the last 30 days that look like receipts, invoices or orders (for example fatura, makbuz, dekont).</li>
        <li>Kasa never sends, deletes or changes email. It asks for read only access.</li>
        <li>Each match becomes an inbox item. Nothing is saved as an expense until you approve it.</li>
        <li>Email text is treated as data. Instructions inside an email are ignored.</li>
        <li>Calendar access is only used to add settle-up reminders you create.</li>
        <li>Disconnect at any time. Kasa deletes its stored Google token.</li>
      </ul>
    </Card>
  );
}
