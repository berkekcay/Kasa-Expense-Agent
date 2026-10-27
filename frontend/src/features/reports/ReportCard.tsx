"use client";

import { Check, Download, Pencil, Pin, PinOff, RefreshCw, Trash2, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useToast } from "@/components/Toast";
import { Alert, Skeleton } from "@/components/ui";
import { ChartView } from "@/features/chat/ChartView";
import { type SavedReport, api, saveBlob } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { dataChanged, useApi } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { reportMessages } from "./messages";

const iconButton =
  "inline-flex size-8 items-center justify-center rounded-lg text-muted transition hover:bg-foreground/5 hover:text-foreground disabled:opacity-40";

/** One saved report, run on today's data when it appears. `compact` hides rename and delete. */
export function ReportCard({ report, compact = false }: { report: SavedReport; compact?: boolean }) {
  const t = useT(reportMessages);
  const notify = useToast();
  const run = useApi(() => api.reports.run(report.id), [report.id]);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(action: () => Promise<unknown>, after?: () => void) {
    setBusy(true);
    setError(null);
    try {
      await action();
      after?.();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  function rename(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const title = String(new FormData(e.currentTarget).get("title") ?? "").trim();
    if (!title) return;
    void act(
      () => api.reports.update(report.id, { title }),
      () => {
        setEditing(false);
        dataChanged("reports");
      },
    );
  }

  const data = run.data;
  return (
    <section className="flex min-w-0 flex-col rounded-2xl border border-border bg-card p-5 shadow-card">
      <div className="mb-3 flex items-start gap-2">
        <div className="min-w-0 flex-1">
          {editing ? (
            <form onSubmit={rename} className="flex items-center gap-1.5">
              <label className="sr-only" htmlFor={`report-title-${report.id}`}>
                {t("titleLabel")}
              </label>
              <input
                id={`report-title-${report.id}`}
                name="title"
                defaultValue={report.title}
                maxLength={200}
                autoFocus
                className="h-8 min-w-0 flex-1 rounded-lg border border-border bg-background px-2 text-sm"
              />
              <button type="submit" aria-label={t("save")} className={iconButton} disabled={busy}>
                <Check className="size-4" />
              </button>
              <button type="button" aria-label={t("cancel")} className={iconButton} onClick={() => setEditing(false)}>
                <X className="size-4" />
              </button>
            </form>
          ) : (
            <h2 className="truncate text-[15px] font-semibold tracking-tight" title={report.title}>
              {report.title}
            </h2>
          )}
          {report.question && report.question !== report.title && (
            <p className="mt-0.5 truncate text-xs text-muted" title={report.question}>
              {report.question}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center">
          <button
            type="button"
            className={iconButton}
            title={t("refresh")}
            aria-label={t("refresh")}
            disabled={run.loading}
            onClick={run.reload}
          >
            <RefreshCw className={`size-4 ${run.loading ? "animate-spin motion-reduce:animate-none" : ""}`} />
          </button>
          <button
            type="button"
            className={iconButton}
            title={report.pinned ? t("unpin") : t("pin")}
            aria-label={report.pinned ? t("unpin") : t("pin")}
            aria-pressed={report.pinned}
            disabled={busy}
            onClick={() =>
              void act(
                () => api.reports.update(report.id, { pinned: !report.pinned }),
                () => dataChanged("reports"),
              )
            }
          >
            {report.pinned ? <PinOff className="size-4" /> : <Pin className="size-4" />}
          </button>
          <button
            type="button"
            className={iconButton}
            title={t("exportCsv")}
            aria-label={t("exportCsv")}
            disabled={busy}
            onClick={() =>
              void act(async () => saveBlob(await api.reports.exportCsv(report.id), `kasa-report-${report.id}.csv`))
            }
          >
            <Download className="size-4" />
          </button>
          {!compact && (
            <>
              <button
                type="button"
                className={iconButton}
                title={t("rename")}
                aria-label={t("rename")}
                onClick={() => setEditing(true)}
              >
                <Pencil className="size-4" />
              </button>
              <button
                type="button"
                className={`${iconButton} hover:text-danger`}
                title={t("delete")}
                aria-label={t("delete")}
                onClick={() => setConfirming(true)}
              >
                <Trash2 className="size-4" />
              </button>
            </>
          )}
        </div>
      </div>

      {confirming && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm">
          <span className="flex-1">{t("confirmDelete")}</span>
          <button
            type="button"
            className="rounded-md px-2 py-1 text-xs font-medium text-danger hover:bg-danger/10"
            onClick={() =>
              void act(
                () => api.reports.remove(report.id),
                () => {
                  notify(t("deleted"), "success");
                  dataChanged("reports");
                },
              )
            }
          >
            {t("delete")}
          </button>
          <button type="button" className="rounded-md px-2 py-1 text-xs hover:bg-foreground/5" onClick={() => setConfirming(false)}>
            {t("keep")}
          </button>
        </div>
      )}

      {error && (
        <Alert tone="error" className="mb-3" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <div className="min-h-0 flex-1">
        {run.error && !data ? (
          <Alert tone="error">{run.error}</Alert>
        ) : !data ? (
          <Skeleton className="h-64 w-full rounded-xl" />
        ) : data.rows.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted">{t("noRows")}</p>
        ) : data.chart ? (
          <ChartView spec={{ ...data.chart, title: "" }} />
        ) : null}
      </div>

      <p className="mt-3 flex flex-wrap items-center gap-x-3 text-xs text-muted">
        {data && <span>{t("lastRun", { time: formatDateTime(data.run_at) })}</span>}
        {data?.truncated && <span>{t("truncated")}</span>}
        {report.pinned && !compact && (
          <span className="inline-flex items-center gap-1 text-accent">
            <Pin aria-hidden className="size-3" /> {t("pinned")}
          </span>
        )}
      </p>
    </section>
  );
}
