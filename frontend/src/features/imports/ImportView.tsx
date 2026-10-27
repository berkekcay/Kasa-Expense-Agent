"use client";

import { ArrowRight, Check, Copy, FileSpreadsheet, FileText, FileUp, Inbox, Rows3, SkipForward, Upload, X } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useState } from "react";
import { api, type ImportResult } from "@/lib/api";
import { useElapsed } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { Alert, Button, Card, PageHeader, Spinner, StatCard, errorMessage } from "@/components/ui";
import { Dropzone, SlowProgress, fileSize } from "@/features/receipts/Dropzone";
import { messages } from "./messages";

const MAX_BYTES = 10 * 1024 * 1024;

const STEPS = [
  { title: "step1Title", text: "step1Text" },
  { title: "step2Title", text: "step2Text" },
  { title: "step3Title", text: "step3Text" },
] as const;

/** The page header. A client component so its text follows the chosen language. */
export function ImportHeader() {
  const t = useT(messages);
  return (
    <PageHeader
      title={t("pageTitle")}
      subtitle={t("pageSubtitle")}
      actions={
        <Link
          href="/inbox"
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm font-medium shadow-card hover:bg-card-hover"
        >
          <Inbox aria-hidden className="size-4" /> {t("openInbox")}
        </Link>
      }
    />
  );
}

export function ImportView() {
  const t = useT(messages);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ name: string; data: ImportResult } | null>(null);
  const elapsed = useElapsed(busy);
  const isPdf = Boolean(file && /\.pdf$/i.test(file.name));
  const step = result ? 2 : busy ? 1 : 0;

  function onPick(picked: File) {
    setError(null);
    setResult(null);
    if (!/\.(csv|txt|pdf|xlsx)$/i.test(picked.name)) {
      setError(t("badType"));
      setFile(null);
      return;
    }
    if (picked.size > MAX_BYTES) {
      setError(t("tooBig"));
      setFile(null);
      return;
    }
    setFile(picked);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api.imports.uploadStatement(file);
      setResult({ name: file.name, data });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const FileIcon = isPdf ? FileText : FileSpreadsheet;

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex min-w-0 flex-col gap-6">
        <Card title={t("fileTitle")} description={t("fileDescription")}>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <Dropzone
              onFile={onPick}
              disabled={busy}
              icon={<FileUp />}
              title={t("dropTitle")}
              hint={t("dropHint")}
              pickers={[
                {
                  id: "statement-file",
                  label: file ? t("chooseAnother") : t("chooseFile"),
                  icon: <Upload aria-hidden />,
                  accept: ".csv,.txt,.pdf,.xlsx,text/csv,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                },
              ]}
            >
              {file && (
                <div className="flex w-full items-center gap-3 rounded-xl bg-foreground/[0.03] p-3 text-left text-sm">
                  <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
                    <FileIcon className="size-5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{file.name}</span>
                    <span className="text-xs text-muted">
                      {fileSize(file.size)} · {isPdf ? t("pdfNote") : t("csvNote")}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setFile(null);
                      setError(null);
                    }}
                    disabled={busy}
                    aria-label={t("removeFile")}
                    title={t("removeFile")}
                    className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 hover:text-foreground disabled:opacity-40"
                  >
                    <X aria-hidden className="size-4" />
                  </button>
                </div>
              )}
            </Dropzone>
            <Button type="submit" disabled={!file || busy} className="h-10">
              {busy ? <Spinner /> : <FileUp aria-hidden className="size-4" />}
              {busy ? t("importing") : t("importStatement")}
            </Button>
            <div aria-live="polite" className="flex flex-col gap-3">
              {busy &&
                (isPdf ? (
                  <SlowProgress title={t("readingPdf")} elapsed={elapsed}>
                    {elapsed < 120 ? t("pdfSlow") : t("pdfStill")}
                  </SlowProgress>
                ) : (
                  <p className="text-sm text-muted">
                    {t("readingLines")}
                    <span aria-hidden className="ml-1 tabular-nums">
                      {t("seconds", { n: elapsed })}
                    </span>
                  </p>
                ))}
              {error && (
                <Alert tone="error" title={t("failed")}>
                  {error}
                </Alert>
              )}
            </div>
          </form>
        </Card>

        <div aria-live="polite">{result && <ImportSummary name={result.name} data={result.data} />}</div>
      </div>

      <Card title={t("howItWorks")}>
        <ol className="flex flex-col">
          {STEPS.map((s, i) => {
            const done = i < step;
            const current = i === step;
            return (
              <li key={s.title} aria-current={current ? "step" : undefined} className="relative flex gap-3 pb-5 last:pb-0">
                {i < STEPS.length - 1 && (
                  <span aria-hidden className={`absolute top-8 bottom-1 left-[13px] w-px ${done ? "bg-accent" : "bg-border"}`} />
                )}
                <span
                  aria-hidden
                  className={`relative flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                    done
                      ? "bg-accent text-accent-foreground"
                      : current
                        ? "bg-accent-soft text-accent ring-1 ring-accent/40"
                        : "bg-foreground/[0.05] text-muted"
                  }`}
                >
                  {done ? <Check className="size-3.5" /> : i + 1}
                </span>
                <div className="min-w-0 pt-0.5 text-sm">
                  <p className={`font-medium ${current || done ? "" : "text-muted"}`}>
                    <span className="sr-only">{done ? t("stepDone") : current ? t("stepCurrent") : ""}</span>
                    {t(s.title)}
                  </p>
                  <p className="mt-0.5 text-muted">{t(s.text)}</p>
                </div>
              </li>
            );
          })}
        </ol>
        <ul className="mt-5 flex flex-col gap-1.5 border-t border-border pt-4 text-sm text-muted">
          <li className="flex gap-2">
            <SkipForward aria-hidden className="mt-0.5 size-4 shrink-0" />
            {t("skippedNote")}
          </li>
          <li className="flex gap-2">
            <Copy aria-hidden className="mt-0.5 size-4 shrink-0" />
            {t("duplicatesNote")}
          </li>
        </ul>
      </Card>
    </div>
  );
}

function ImportSummary({ name, data }: { name: string; data: ImportResult }) {
  const t = useT(messages);
  return (
    <Card title={t("resultTitle")} description={name}>
      <div className="flex flex-col gap-5">
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <StatCard icon={<Rows3 />} label={t("linesRead")} value={data.lines} />
          <StatCard icon={<Inbox />} label={t("newInInbox")} value={data.created} />
          <StatCard icon={<Copy />} label={t("duplicates")} value={data.duplicates} />
          <StatCard icon={<SkipForward />} label={t("skipped")} value={data.skipped} />
        </div>
        {data.created > 0 ? (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-accent/30 bg-accent-soft px-4 py-3 text-sm">
            <span aria-hidden className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
              <Inbox className="size-4" />
            </span>
            <p className="min-w-0 flex-1">
              <strong className="font-semibold">{data.created}</strong> {t("waiting", { n: data.created })}
            </p>
            <Link
              href="/inbox"
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3 text-sm font-medium text-accent-foreground shadow-card hover:brightness-110"
            >
              {t("openTheInbox")} <ArrowRight aria-hidden className="size-4" />
            </Link>
          </div>
        ) : (
          <Alert tone="info">
            {t("noNew")} {data.duplicates > 0 ? t("allBefore") : t("noLines")}
          </Alert>
        )}
        {data.errors.length > 0 && (
          <div className="rounded-xl border border-border p-4">
            <p className="text-sm font-medium">{t("unreadable", { n: data.errors.length })}</p>
            <ul className="mt-2 flex flex-col gap-1 text-sm text-muted">
              {data.errors.map((err, i) => (
                <li key={i} className="flex gap-2">
                  <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-current" />
                  {err}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}
