"use client";

import Link from "next/link";
import { type ChangeEvent, type FormEvent, useState } from "react";
import { api, type ImportResult } from "@/lib/api";
import { useElapsed } from "@/lib/hooks";
import { Alert, Button, Card, Spinner, Stat, errorMessage } from "@/components/ui";

const MAX_BYTES = 10 * 1024 * 1024;

export function ImportView() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ name: string; data: ImportResult } | null>(null);
  const elapsed = useElapsed(busy);
  const isPdf = Boolean(file && /\.pdf$/i.test(file.name));

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    setError(null);
    setResult(null);
    if (picked && !/\.(csv|txt|pdf)$/i.test(picked.name)) {
      setError("Upload a CSV or PDF statement.");
      setFile(null);
      return;
    }
    if (picked && picked.size > MAX_BYTES) {
      setError("The file is larger than 10 MB.");
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

  return (
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <Card title="Statement file">
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">CSV or PDF, up to 10 MB</span>
            <input
              type="file"
              accept=".csv,.txt,.pdf,text/csv,application/pdf"
              onChange={onPick}
              disabled={busy}
              className="text-sm file:mr-3 file:h-9 file:rounded-lg file:border file:border-border file:bg-background file:px-3 file:text-sm file:text-foreground"
            />
          </label>
          <Button type="submit" disabled={!file || busy} className="h-10">
            {busy ? (
              <>
                <Spinner /> Importing
              </>
            ) : (
              "Import statement"
            )}
          </Button>
          <div aria-live="polite">
            {busy && (
              <p className="text-sm text-muted">
                {isPdf
                  ? "Kasa is reading the PDF. On the dev server this can take 30 to 120 seconds."
                  : "Reading the lines."}
                <span aria-hidden className="ml-1 tabular-nums">
                  ({elapsed} s)
                </span>
              </p>
            )}
            {error && (
              <Alert tone="error" title="Import failed">
                {error}
              </Alert>
            )}
          </div>
          <div className="text-sm text-muted">
            <p>How it works:</p>
            <ul className="mt-1 list-disc pl-5">
              <li>Each spending line becomes an inbox item. Nothing is saved as an expense until you approve it.</li>
              <li>Payments to the card and refunds are skipped.</li>
              <li>Lines you already imported are recognised and not added twice.</li>
              <li>CSV files are read directly. PDF statements are read by the AI model.</li>
            </ul>
          </div>
        </form>
      </Card>

      <Card title="Result">
        <div aria-live="polite">
          {!result ? (
            <p className="text-sm text-muted">Upload a statement to see what was found.</p>
          ) : (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted">{result.name}</p>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat label="Lines read" value={result.data.lines} />
                <Stat label="New in inbox" value={result.data.created} />
                <Stat label="Duplicates" value={result.data.duplicates} />
                <Stat label="Skipped" value={result.data.skipped} />
              </div>
              {result.data.created > 0 ? (
                <Alert tone="success">
                  {result.data.created} {result.data.created === 1 ? "item is" : "items are"} waiting for review.{" "}
                  <Link href="/inbox" className="font-medium text-accent underline">
                    Open the inbox
                  </Link>
                </Alert>
              ) : (
                <Alert tone="info">
                  No new items.{" "}
                  {result.data.duplicates > 0 ? "Everything here was imported before." : "No spending lines were found."}
                </Alert>
              )}
              {result.data.errors.length > 0 && (
                <div>
                  <p className="text-sm font-medium">Lines that could not be read</p>
                  <ul className="mt-1 list-disc pl-5 text-sm text-muted">
                    {result.data.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
