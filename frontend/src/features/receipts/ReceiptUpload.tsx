"use client";

import { type ChangeEvent, type FormEvent, useEffect, useState } from "react";
import { api, type ReceiptResult } from "@/lib/api";
import { Button, Card, ErrorText, Money, errorMessage } from "@/components/ui";

const ACCEPT = "image/jpeg,image/png,image/webp,image/heic,image/heif";

export function ReceiptUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReceiptResult | null>(null);

  // Release the object URL when the preview changes or the page unmounts.
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    setFile(picked);
    setPreview(picked ? URL.createObjectURL(picked) : null);
    setResult(null);
    setError(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
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
    <div className="grid gap-6 lg:grid-cols-2">
      <Card title="Upload">
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <input
            type="file"
            accept={ACCEPT}
            capture="environment"
            onChange={onPick}
            className="text-sm file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm"
          />
          {preview && (
            // eslint-disable-next-line @next/next/no-img-element -- local blob preview, nothing to optimise
            <img src={preview} alt="Receipt preview" className="max-h-80 w-full rounded-lg border border-border object-contain" />
          )}
          <Button type="submit" disabled={!file || busy}>
            {busy ? "Reading receipt…" : "Read & save"}
          </Button>
          <ErrorText error={error} />
        </form>
      </Card>

      <Card title="Result">
        {!expense ? (
          <p className="text-sm text-muted">
            The receipt agent reads the photo, then a tool saves the expense with exact amounts.
          </p>
        ) : (
          <div className="flex flex-col gap-3 text-sm">
            <div className="flex items-baseline justify-between gap-4">
              <div>
                <p className="text-base font-medium">{expense.merchant}</p>
                <p className="text-muted">{expense.expense_date}</p>
              </div>
              <p className="text-lg font-semibold">
                <Money amount={expense.total} currency={expense.currency} />
              </p>
            </div>
            {expense.items.length > 0 && (
              <ul className="divide-y divide-border rounded-lg border border-border">
                {expense.items.map((item, i) => (
                  <li key={i} className="flex justify-between gap-4 px-3 py-1.5">
                    <span>
                      {item.description}
                      {item.quantity !== "1" && <span className="text-muted"> × {item.quantity}</span>}
                    </span>
                    <span className="tabular-nums">{item.amount}</span>
                  </li>
                ))}
              </ul>
            )}
            {result.warnings.map((w) => (
              <p key={w} className="text-danger">
                {w}
              </p>
            ))}
            {result.agent_message && <p className="text-muted">{result.agent_message}</p>}
          </div>
        )}
      </Card>
    </div>
  );
}
