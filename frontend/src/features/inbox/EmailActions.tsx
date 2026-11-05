"use client";

// Inbox header actions for email: upload one email saved as .eml, and, when a mailbox is
// connected in Settings, check it now. Both put purchases in the inbox for approval.

import { MailPlus, RefreshCw } from "lucide-react";
import { type ChangeEvent, useRef, useState } from "react";
import { api, type SyncResult } from "@/lib/api";
import { dataChanged, useApi } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useToast } from "@/components/Toast";
import { Button, Spinner, errorMessage } from "@/components/ui";
import { mailMessages } from "@/features/settings/mailMessages";

export function EmailActions() {
  const t = useT(mailMessages);
  const notify = useToast();
  const mail = useApi(() => api.integrations.mailStatus(), []);
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"upload" | "sync" | null>(null);

  function report(res: SyncResult, single: boolean) {
    if (res.created > 0) dataChanged("inbox");
    if (res.error) notify(res.error, "warning");
    else if (!single)
      notify(
        t("syncSummary", { fetched: res.fetched, created: res.created, ignored: res.ignored, duplicates: res.duplicates }),
        "success",
      );
    else if (res.created > 0) notify(t("emailAdded"), "success");
    else if (res.duplicates > 0) notify(t("emailDuplicate"), "info");
    else notify(t("emailNotPurchase"), "info");
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy("upload");
    try {
      report(await api.imports.uploadEmail(file), true);
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function syncNow() {
    setBusy("sync");
    try {
      report(await api.integrations.mailSync(), false);
      mail.reload();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      {mail.data?.connected && (
        <Button variant="ghost" onClick={syncNow} disabled={busy !== null} title={mail.data.address ?? undefined}>
          {busy === "sync" ? <Spinner className="size-3.5" /> : <RefreshCw aria-hidden className="size-4" />}
          {busy === "sync" ? t("checking") : t("checkNow")}
        </Button>
      )}
      <Button variant="ghost" onClick={() => input.current?.click()} disabled={busy !== null} title={t("uploadHint")}>
        {busy === "upload" ? <Spinner className="size-3.5" /> : <MailPlus aria-hidden className="size-4" />}
        {busy === "upload" ? t("uploadingEmail") : t("uploadEmail")}
      </Button>
      <input ref={input} type="file" accept=".eml,message/rfc822" className="sr-only" tabIndex={-1} aria-hidden onChange={onFile} />
    </>
  );
}
