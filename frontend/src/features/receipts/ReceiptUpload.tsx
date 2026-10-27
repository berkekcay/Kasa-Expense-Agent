"use client";

import { ArrowRight, Camera, CircleCheck, ImageUp, Plus, RotateCcw, ScanLine, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";
import { api, type ReceiptResult } from "@/lib/api";
import { categoryLabel, common, sourceLabel } from "@/lib/commonMessages";
import { formatDate } from "@/lib/format";
import { useApi, useElapsed } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { Alert, Badge, Button, Card, Empty, Money, PageHeader, Skeleton, cardLinkClass, errorMessage } from "@/components/ui";
import { CategoryIcon } from "@/features/expenses/CategoryIcon";
import { ConversionNote } from "@/features/expenses/ExpenseList";
import { Markdown } from "@/features/chat/Markdown";
import { Dropzone, SlowProgress, fileSize } from "./Dropzone";
import { messages } from "./messages";

const ALLOWED = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];
const MAX_BYTES = 10 * 1024 * 1024;

/** The page header. A client component so its text follows the chosen language. */
export function ReceiptsHeader() {
  const t = useT(messages);
  return (
    <PageHeader
      title={t("pageTitle")}
      subtitle={t("pageSubtitle")}
      actions={
        <Link
          href="/expenses#add"
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm font-medium shadow-card hover:bg-card-hover"
        >
          <Plus aria-hidden className="size-4" /> {t("addByHand")}
        </Link>
      }
    />
  );
}

export function ReceiptUpload() {
  const t = useT(messages);
  const tc = useT(common);
  const health = useApi(() => api.health(), []);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReceiptResult | null>(null);
  const elapsed = useElapsed(busy);
  const agentsOff = health.data?.agents_enabled === false;

  // Release the object URL when the preview changes or the page unmounts.
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  function onPick(picked: File) {
    setResult(null);
    setError(null);
    if (picked.type && !ALLOWED.includes(picked.type)) {
      setError(t("badType"));
      return;
    }
    if (picked.size > MAX_BYTES) {
      setError(t("tooBig"));
      return;
    }
    setFile(picked);
    setPreview(URL.createObjectURL(picked));
  }

  function clear() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.uploadReceipt(file));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const expense = result?.expense;

  return (
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <Card title={t("photoTitle")} description={t("photoDescription")}>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {agentsOff && (
            <Alert tone="warning" title={t("offTitle")}>
              {t("offText")}
            </Alert>
          )}
          <Dropzone
            onFile={onPick}
            disabled={busy || agentsOff}
            icon={<ImageUp />}
            title={t("dropTitle")}
            hint={t("dropHint")}
            pickers={[
              {
                id: "receipt-camera",
                label: file ? t("takeAnother") : t("takePhoto"),
                icon: <Camera aria-hidden />,
                accept: "image/*",
                capture: "environment",
                primary: !file,
                touchOnly: true,
              },
              {
                id: "receipt-file",
                label: file ? t("chooseAnother") : t("chooseFile"),
                icon: <ImageUp aria-hidden />,
                accept: ALLOWED.join(","),
              },
            ]}
          >
            {file && preview && (
              <div className="flex w-full flex-col gap-3">
                <div className="relative overflow-hidden rounded-xl bg-foreground/[0.04]">
                  {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview, nothing to optimise */}
                  <img
                    src={preview}
                    alt={t("previewAlt")}
                    className={`mx-auto max-h-96 w-full object-contain transition ${busy ? "opacity-50" : ""}`}
                  />
                  {busy && <span aria-hidden className="skeleton absolute inset-0 opacity-30" />}
                </div>
                <div className="flex items-center gap-2 text-left text-sm">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{file.name}</span>
                    <span className="text-xs text-muted">{fileSize(file.size)}</span>
                  </span>
                  <button
                    type="button"
                    onClick={clear}
                    disabled={busy}
                    aria-label={t("removePhoto")}
                    title={t("removePhoto")}
                    className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 hover:text-foreground disabled:opacity-40"
                  >
                    <X aria-hidden className="size-4" />
                  </button>
                </div>
              </div>
            )}
          </Dropzone>
          <Button type="submit" disabled={!file || busy || agentsOff} className="h-10">
            <ScanLine aria-hidden className="size-4" />
            {busy ? t("reading") : t("readAndSave")}
          </Button>
          <div aria-live="polite" className="flex flex-col gap-3">
            {busy && (
              <SlowProgress title={t("reading")} elapsed={elapsed}>
                {elapsed < 120 ? t("readingSlow") : t("stillReading")}
              </SlowProgress>
            )}
            {error && (
              <Alert tone="error" title={t("errorTitle")}>
                {error}
              </Alert>
            )}
          </div>
        </form>
      </Card>

      <Card title={t("result")} description={expense ? undefined : t("resultDescription")}>
        <div aria-live="polite">
          {busy ? (
            <ResultSkeleton label={t("reading")} />
          ) : !expense ? (
            <Empty icon={<ScanLine />}>
              {t("emptyResult")}
            </Empty>
          ) : (
            <div className="flex flex-col gap-5 text-sm">
              <p className="flex items-center gap-1.5 font-medium text-positive">
                <CircleCheck aria-hidden className="size-4" /> {t("saved")}
              </p>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3">
                  <CategoryIcon category={expense.category} size="lg" />
                  <div className="min-w-0">
                    <p className="truncate text-lg font-semibold tracking-tight">{expense.merchant}</p>
                    <p className="text-muted">
                      {formatDate(expense.expense_date)}
                      {expense.category && ` · ${categoryLabel(expense.category)}`}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <Money amount={expense.total} currency={expense.currency} className="text-2xl font-semibold tracking-tight tabular-nums" />
                  <ConversionNote e={expense} />
                </div>
              </div>

              {expense.items.length > 0 ? (
                <div className="overflow-hidden rounded-xl border border-border">
                  <table className="w-full text-sm">
                    <caption className="sr-only">{t("linesCaption")}</caption>
                    <thead className="bg-foreground/[0.03] text-xs text-muted">
                      <tr>
                        <th scope="col" className="px-3 py-2 text-left font-medium">
                          {t("item")}
                        </th>
                        <th scope="col" className="px-3 py-2 text-right font-medium">
                          {t("qty")}
                        </th>
                        <th scope="col" className="px-3 py-2 text-right font-medium">
                          {t("amount")}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {expense.items.map((item, i) => (
                        <tr key={i}>
                          <td className="px-3 py-2">{item.description}</td>
                          <td className="px-3 py-2 text-right text-muted tabular-nums">{item.quantity}</td>
                          <td className="px-3 py-2 text-right">
                            <Money amount={item.amount} currency={expense.currency} className="tabular-nums" />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="border-t border-border-strong">
                      <tr>
                        <th scope="row" colSpan={2} className="px-3 py-2.5 text-left font-semibold">
                          {tc("total")}
                        </th>
                        <td className="px-3 py-2.5 text-right font-semibold">
                          <Money amount={expense.total} currency={expense.currency} className="tabular-nums" />
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ) : (
                <p className="rounded-xl border border-dashed border-border px-3 py-4 text-center text-muted">
                  {t("noLines")}
                </p>
              )}

              {result.warnings.length > 0 && (
                <div className="flex flex-col gap-2">
                  {result.warnings.map((w) => (
                    <Alert key={w} tone="warning">
                      {w}
                    </Alert>
                  ))}
                </div>
              )}

              {result.agent_message && (
                <div className="rounded-xl bg-foreground/[0.04] px-4 py-3">
                  <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted">
                    <Sparkles aria-hidden className="size-3.5 text-accent" /> {t("kasaSays")}
                  </p>
                  <div className="text-foreground/90">
                    <Markdown text={result.agent_message} />
                  </div>
                </div>
              )}

              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
                <span className="flex flex-wrap gap-1.5">
                  <Badge>{sourceLabel("receipt")}</Badge>
                  {expense.items.length > 0 && (
                    <Badge>{t("lineCount", { n: expense.items.length })}</Badge>
                  )}
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  <Button variant="ghost" size="sm" onClick={clear}>
                    <RotateCcw aria-hidden className="size-3.5" /> {t("scanAnother")}
                  </Button>
                  <Link href="/expenses" className={cardLinkClass}>
                    {t("seeAllExpenses")} <ArrowRight aria-hidden className="size-3.5" />
                  </Link>
                </span>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

function ResultSkeleton({ label }: { label: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <Skeleton className="size-11 rounded-xl" />
        <div className="flex flex-1 flex-col gap-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-3 w-28" />
        </div>
        <Skeleton className="h-6 w-24" />
      </div>
      <div className="flex flex-col gap-2.5 rounded-xl border border-border p-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex justify-between gap-4">
            <Skeleton className="h-3.5 w-1/2" />
            <Skeleton className="h-3.5 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}
