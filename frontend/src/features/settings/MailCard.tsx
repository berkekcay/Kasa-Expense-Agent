"use client";

// Purchase emails without Google Cloud: any mailbox over IMAP with an app password. The
// server checks the password before saving it (encrypted) and only ever reads mail.

import { ExternalLink, RefreshCw, Unplug } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api, type MailStatus, type SyncResult } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { dataChanged, useApi } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useToast } from "@/components/Toast";
import { Alert, Async, Badge, Button, Card, ErrorText, Field, Skeleton, Spinner, errorMessage } from "@/components/ui";
import { mailMessages } from "./mailMessages";

const KNOWN_DOMAINS = new Set([
  "gmail.com",
  "googlemail.com",
  "outlook.com",
  "hotmail.com",
  "live.com",
  "yandex.com",
  "yandex.com.tr",
  "icloud.com",
  "yahoo.com",
]);
const APP_PASSWORDS_URL = "https://myaccount.google.com/apppasswords";

function needsServer(address: string): boolean {
  const domain = address.split("@")[1]?.trim().toLowerCase();
  return Boolean(domain) && !KNOWN_DOMAINS.has(domain);
}

export function SyncSummary({ result, onDismiss }: { result: SyncResult; onDismiss: () => void }) {
  const t = useT(mailMessages);
  return (
    <Alert tone={result.error ? "warning" : "success"} title={t("syncDone")} onDismiss={onDismiss}>
      {t("syncSummary", {
        fetched: result.fetched,
        created: result.created,
        ignored: result.ignored,
        duplicates: result.duplicates,
      })}
      {result.failed > 0 && t("syncFailed", { n: result.failed })}.
      {result.error && <span className="mt-1 block">{result.error}</span>}
    </Alert>
  );
}

export function MailCard() {
  const status = useApi(() => api.integrations.mailStatus(), []);
  const t = useT(mailMessages);
  return (
    <Card title={t("mailTitle")} description={t("mailDesc")}>
      <Async {...status} label={t("mailLoading")} fallback={<Skeleton className="h-24 w-full" />}>
        {(s: MailStatus) =>
          s.connected ? (
            <Connected status={s} onChange={status.reload} />
          ) : s.ready ? (
            <ConnectForm onConnected={status.reload} />
          ) : (
            <Alert tone="info">{t("notReady")}</Alert>
          )
        }
      </Async>
    </Card>
  );
}

function ConnectForm({ onConnected }: { onConnected: () => void }) {
  const t = useT(mailMessages);
  const notify = useToast();
  const [address, setAddress] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const password = String(form.get("password") ?? "");
    const host = String(form.get("host") ?? "").trim();
    if (!address.includes("@") || !password.trim()) {
      setError(t("errFields"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await api.integrations.mailConnect({ address: address.trim(), password, host: host || null });
      notify(t("connectedToast", { address: saved.address ?? address }), "success");
      onConnected();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          label={t("address")}
          name="address"
          type="email"
          required
          autoComplete="email"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
        />
        <Field
          label={t("appPassword")}
          name="password"
          type="password"
          required
          autoComplete="off"
          spellCheck={false}
          hint={t("appPasswordHint")}
        />
        {needsServer(address) && (
          <Field label={t("server")} name="host" placeholder="imap.example.edu.tr" hint={t("serverHint")} />
        )}
      </div>
      <ErrorText error={error} />
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={busy}>
          {busy && <Spinner className="size-3.5" />}
          {busy ? t("connecting") : t("connect")}
        </Button>
        <a
          href={APP_PASSWORDS_URL}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-sm text-accent underline-offset-2 hover:underline"
        >
          {t("appPasswordLink")} <ExternalLink aria-hidden className="size-3.5" />
        </a>
      </div>
    </form>
  );
}

function Connected({ status, onChange }: { status: MailStatus; onChange: () => void }) {
  const t = useT(mailMessages);
  const notify = useToast();
  const [busy, setBusy] = useState<"sync" | "disconnect" | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);

  async function syncNow() {
    setBusy("sync");
    setResult(null);
    try {
      const res = await api.integrations.mailSync();
      setResult(res);
      if (res.created > 0) dataChanged("inbox");
      onChange();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function disconnect() {
    setBusy("disconnect");
    try {
      await api.integrations.mailDisconnect();
      notify(t("disconnectedToast"), "success");
      onChange();
    } catch (err) {
      notify(errorMessage(err), "error");
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4 text-sm">
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[auto_1fr]">
        <dt className="text-muted">{t("status")}</dt>
        <dd className="flex min-w-0 flex-wrap items-center gap-2">
          <Badge tone="positive">{t("connected")}</Badge>
          <span className="truncate">{status.address}</span>
          <span className="text-muted">({status.host})</span>
        </dd>
        <dt className="text-muted">{t("lastCheck")}</dt>
        <dd>
          {status.last_sync_at ? formatDateTime(status.last_sync_at) : t("never")}
          <span className="mt-0.5 block text-xs text-muted">{t("autoNote")}</span>
        </dd>
      </dl>
      {status.last_error && !result && <Alert tone="warning">{status.last_error}</Alert>}
      <div className="flex flex-wrap gap-2 border-t border-border pt-4">
        <Button variant="ghost" onClick={syncNow} disabled={busy !== null}>
          {busy === "sync" ? <Spinner className="size-3.5" /> : <RefreshCw aria-hidden className="size-3.5" />}
          {busy === "sync" ? t("checking") : t("checkNow")}
        </Button>
        {confirm ? (
          <span className="flex flex-wrap items-center gap-2 sm:ml-auto">
            <span className="text-muted">{t("confirmDisconnect")}</span>
            <Button variant="danger" onClick={disconnect} disabled={busy !== null}>
              {t("forget")}
            </Button>
            <Button variant="ghost" onClick={() => setConfirm(false)}>
              {t("keep")}
            </Button>
          </span>
        ) : (
          <Button variant="subtle" className="sm:ml-auto" onClick={() => setConfirm(true)} disabled={busy !== null}>
            <Unplug aria-hidden className="size-3.5" /> {t("disconnect")}
          </Button>
        )}
      </div>
      <div aria-live="polite">
        {busy === "sync" && <p className="text-muted">{t("checkSlow")}</p>}
        {result && <SyncSummary result={result} onDismiss={() => setResult(null)} />}
      </div>
    </div>
  );
}
