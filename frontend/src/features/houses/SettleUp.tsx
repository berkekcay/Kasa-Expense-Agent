"use client";

import { type FormEvent, useState } from "react";
import { ApiError, api, type Balances, type House, type Settlement } from "@/lib/api";
import { formatDateTime, normalizeAmount } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { Alert, Button, Empty, ErrorText, Field, Money, SelectField, errorMessage } from "@/components/ui";

type Draft = { from_user: string; to_user: string; amount: string };

export function BalancesPanel({
  house,
  balances,
  me,
  name,
  onChanged,
}: {
  house: House;
  balances: Balances;
  me: string;
  name: (id: string) => string;
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const cur = balances.currency;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h3 className="mb-2 text-sm font-medium">Balances</h3>
        <ul className="flex flex-col divide-y divide-border text-sm">
          {balances.balances.map((b) => {
            const you = b.user_id === me;
            const who = you ? "You" : name(b.user_id);
            const abs = b.balance.replace(/^-/, "");
            return (
              <li key={b.user_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className={you ? "font-medium" : ""}>{who}</span>
                {b.balance_minor === 0 ? (
                  <span className="text-muted">{you ? "are settled up" : "is settled up"}</span>
                ) : b.balance_minor > 0 ? (
                  <span>
                    {you ? "are owed" : "is owed"} <Money amount={abs} currency={cur} className="font-semibold text-positive" />
                  </span>
                ) : (
                  <span>
                    {you ? "owe" : "owes"} <Money amount={abs} currency={cur} className="font-semibold text-danger" />
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-medium">Suggested transfers</h3>
        {balances.transfers.length === 0 ? (
          <p className="text-sm text-muted">Everyone is settled up.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {balances.transfers.map((t, i) => (
              <li key={i} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2">
                <span>
                  <strong className="font-medium">{t.from_user === me ? "You" : name(t.from_user)}</strong>{" "}
                  {t.from_user === me ? "pay" : "pays"}{" "}
                  <strong className="font-medium">{t.to_user === me ? "you" : name(t.to_user)}</strong>{" "}
                  <Money amount={t.amount} currency={cur} className="font-semibold" />
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setDraft({ from_user: t.from_user, to_user: t.to_user, amount: t.amount })}
                >
                  Record payment
                </Button>
              </li>
            ))}
          </ul>
        )}
        {!draft && house.members.length > 1 && (
          <Button
            variant="subtle"
            size="sm"
            className="mt-2"
            onClick={() =>
              setDraft({ from_user: me, to_user: house.members.find((m) => m.user_id !== me)?.user_id ?? "", amount: "" })
            }
          >
            Record another payment
          </Button>
        )}
      </div>

      {draft && (
        <PaymentForm
          key={`${draft.from_user}-${draft.to_user}-${draft.amount}`}
          house={house}
          draft={draft}
          me={me}
          onCancel={() => setDraft(null)}
          onSaved={() => {
            setDraft(null);
            onChanged();
          }}
        />
      )}
    </div>
  );
}

function PaymentForm({
  house,
  draft,
  me,
  onCancel,
  onSaved,
}: {
  house: House;
  draft: Draft;
  me: string;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const notify = useToast();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    const amount = normalizeAmount(String(d.get("amount") ?? ""));
    const from = String(d.get("from_user"));
    const to = String(d.get("to_user"));
    if (!amount) {
      setError("Enter an amount like 43,33.");
      return;
    }
    if (from === to) {
      setError("Pick two different people.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.recordSettlement(house.id, {
        from_user: from,
        to_user: to,
        amount,
        note: String(d.get("note") ?? "").trim() || undefined,
        allow_overpayment: d.get("allow_overpayment") === "on",
      });
      notify("Payment recorded.", "success");
      onSaved();
    } catch (err) {
      setConflict(err instanceof ApiError && err.status === 409);
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 rounded-lg border border-accent/40 p-3 sm:p-4" aria-label="Record a payment">
      <h3 className="text-sm font-medium">Record a payment</h3>
      <div className="grid gap-3 sm:grid-cols-3">
        <SelectField label="Who paid" name="from_user" defaultValue={draft.from_user}>
          {house.members.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.display_name}
              {m.user_id === me ? " (you)" : ""}
            </option>
          ))}
        </SelectField>
        <SelectField label="Who got it" name="to_user" defaultValue={draft.to_user}>
          {house.members.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.display_name}
              {m.user_id === me ? " (you)" : ""}
            </option>
          ))}
        </SelectField>
        <Field
          label={`Amount (${house.currency})`}
          name="amount"
          defaultValue={draft.amount}
          required
          inputMode="decimal"
          autoComplete="off"
        />
      </div>
      <Field label="Note (optional)" name="note" maxLength={500} placeholder="Bank transfer" />
      {conflict && (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" name="allow_overpayment" className="mt-0.5 size-4 accent-[var(--accent)]" />
          This is an advance or a loan, so record it even though it is more than the open debt.
        </label>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving" : "Record payment"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
      <ErrorText error={error} />
    </form>
  );
}

export function SettlementsPanel({
  house,
  settlements,
  me,
  name,
  onChanged,
}: {
  house: House;
  settlements: Settlement[];
  me: string;
  name: (id: string) => string;
  onChanged: () => void;
}) {
  const notify = useToast();
  const [confirm, setConfirm] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  async function undo(s: Settlement) {
    setBusy(true);
    try {
      await api.deleteSettlement(house.id, s.id);
      notify("Payment removed. Balances are back to before it.", "success");
      setConfirm(null);
      onChanged();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  }

  if (settlements.length === 0) return <Empty>No payments recorded yet. Record one from a suggested transfer.</Empty>;
  return (
    <ul className="flex flex-col divide-y divide-border text-sm">
      {settlements.map((s) => (
        <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0 last:pb-0">
          <div className="min-w-0">
            <p>
              <strong className="font-medium">{s.from_user === me ? "You" : name(s.from_user)}</strong> paid{" "}
              <strong className="font-medium">{s.to_user === me ? "you" : name(s.to_user)}</strong>{" "}
              <Money amount={s.amount} currency={s.currency} className="font-semibold" />
            </p>
            <p className="text-muted">
              {formatDateTime(s.created_at)} · recorded by {s.created_by === me ? "you" : name(s.created_by)}
              {s.note && ` · ${s.note}`}
            </p>
          </div>
          {s.created_by === me &&
            (confirm === s.id ? (
              <span className="flex gap-2">
                <Button size="sm" variant="danger" onClick={() => undo(s)} disabled={busy}>
                  Undo payment
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>
                  Keep
                </Button>
              </span>
            ) : (
              <Button size="sm" variant="subtle" onClick={() => setConfirm(s.id)}>
                Undo
              </Button>
            ))}
        </li>
      ))}
      <li className="pt-3">
        <Alert tone="info">Only the person who recorded a payment can undo it.</Alert>
      </li>
    </ul>
  );
}
