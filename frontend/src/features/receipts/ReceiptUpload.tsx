"use client";

import Link from "next/link";
import { type ChangeEvent, type FormEvent, useEffect, useState } from "react";
import { api, type ReceiptResult } from "@/lib/api";
import { capitalize, formatDate } from "@/lib/format";
import { useApi, useElapsed } from "@/lib/hooks";
import { Alert, Badge, Button, Card, Money, Spinner, errorMessage } from "@/components/ui";
import { ConversionNote } from "@/features/expenses/ExpenseList";
import { Markdown } from "@/features/chat/Markdown";

const ALLOWED = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];
const MAX_BYTES = 10 * 1024 * 1024;

const pickerLabel =
  "inline-flex h-10 cursor-pointer items-center justify-center rounded-lg px-4 text-sm font-medium peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--accent)] peer-disabled:cursor-not-allowed peer-disabled:opacity-50";

export function ReceiptUpload() {
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

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    e.target.value = ""; // picking the same photo again still fires change
    setResult(null);
    setError(null);
    if (!picked) return;
    if (picked.type && !ALLOWED.includes(picked.type)) {
      setError("Use a JPEG, PNG, WebP or HEIC photo.");
      return;
    }
    if (picked.size > MAX_BYTES) {
      setError("The photo is larger than 10 MB. Take it again at a lower resolution.");
      return;
    }
    setFile(picked);
    setPreview(URL.createObjectURL(picked));
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
      <Card title="Photo">
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {agentsOff && (
            <Alert tone="warning" title="Receipt reading is off">
              The server has no AI model configured, so it cannot read photos right now. You can still add expenses by hand on
              the Expenses page.
            </Alert>
          )}
          <div className="flex flex-wrap gap-2">
            <span>
              <input
                id="receipt-camera"
                type="file"
                accept="image/*"
                capture="environment"
                onChange={onPick}
                disabled={busy || agentsOff}
                className="peer sr-only"
              />
              <label htmlFor="receipt-camera" className={`${pickerLabel} bg-accent text-accent-foreground hover:opacity-90`}>
                Take a photo
              </label>
            </span>
            <span>
              <input
                id="receipt-file"
                type="file"
                accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
                onChange={onPick}
                disabled={busy || agentsOff}
                className="peer sr-only"
              />
              <label htmlFor="receipt-file" className={`${pickerLabel} border border-border hover:bg-foreground/5`}>
                Choose a file
              </label>
            </span>
          </div>
          {file && <p className="text-sm text-muted">{file.name}</p>}
          {preview && (
            // eslint-disable-next-line @next/next/no-img-element -- local blob preview, nothing to optimise
            <img src={preview} alt="Receipt preview" className="max-h-80 w-full rounded-lg border border-border object-contain" />
          )}
          <Button type="submit" disabled={!file || busy || agentsOff} className="h-10">
            {busy ? (
              <>
                <Spinner /> Reading the receipt
              </>
            ) : (
              "Read and save"
            )}
          </Button>
          <div aria-live="polite">
            {busy && (
              <p className="text-sm text-muted">
                Kasa is reading the receipt. On the dev server this can take 30 to 120 seconds. Keep this page open.
                <span aria-hidden className="ml-1 tabular-nums">
                  ({elapsed} s)
                </span>
              </p>
            )}
            {error && (
              <Alert tone="error" title="Could not save this receipt">
                {error}
              </Alert>
            )}
          </div>
        </form>
      </Card>

      <Card title="Result">
        <div aria-live="polite">
          {!expense ? (
            <p className="text-sm text-muted">
              Kasa reads the merchant, date, lines and total, then saves the expense with exact amounts. Check the result
              here.
            </p>
          ) : (
            <div className="flex flex-col gap-4 text-sm">
              <Alert tone="success">Saved as an expense.</Alert>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-base font-semibold">{expense.merchant}</p>
                  <p className="text-muted">
                    {formatDate(expense.expense_date)}
                    {expense.category && ` · ${capitalize(expense.category)}`}
                  </p>
                </div>
                <div className="text-right">
                  <Money amount={expense.total} currency={expense.currency} className="text-xl font-semibold" />
                  <ConversionNote e={expense} />
                </div>
              </div>
              {expense.items.length > 0 ? (
                <ul className="divide-y divide-border rounded-lg border border-border">
                  {expense.items.map((item, i) => (
                    <li key={i} className="flex justify-between gap-4 px-3 py-1.5">
                      <span className="min-w-0">
                        {item.description}
                        {item.quantity !== "1" && <span className="text-muted"> × {item.quantity}</span>}
                      </span>
                      <Money amount={item.amount} currency={expense.currency} className="tabular-nums" />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted">No separate lines were read.</p>
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
                <div>
                  <Badge>Kasa says</Badge>
                  <div className="mt-1 text-muted">
                    <Markdown text={result.agent_message} />
                  </div>
                </div>
              )}
              <Link href="/expenses" className="text-accent hover:underline">
                See all expenses
              </Link>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
