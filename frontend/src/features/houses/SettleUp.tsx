"use client";

import { ArrowRight, CircleCheck, HandCoins, Plus, Undo2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { ApiError, api, type Balances, type House, type Settlement } from "@/lib/api";
import { common } from "@/lib/commonMessages";
import { formatDateTime, formatMoney, normalizeAmount } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useToast } from "@/components/Toast";
import { Swatch } from "@/components/charts";
import { Button, Empty, ErrorText, Field, Money, SelectField, errorMessage } from "@/components/ui";
import { houseMessages } from "./messages";
import { MemberAvatar } from "./parts";

type Draft = { from_user: string; to_user: string; amount: string };

/**
 * Who is owed and who owes: one bar per member around a zero line. Owed money grows to the
 * right, debt to the left. The amounts are written next to every bar, and each row has a
 * sentence for screen readers, so the bars themselves are decoration.
 */
export function BalanceBars({
  house,
  balances,
  me,
  name,
}: {
  house: House;
  balances: Balances;
  me: string;
  name: (id: string) => string;
}) {
  const t = useT(houseMessages);
  const cur = balances.currency;
  const rows = [...balances.balances].sort((a, b) => b.balance_minor - a.balance_minor);
  const max = Math.max(1, ...rows.map((b) => Math.abs(b.balance_minor)));

  if (rows.length === 0) return <Empty>{t("noMembers")}</Empty>;
  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-hidden>
        <li className="flex items-center gap-1.5">
          <Swatch color="var(--diverge-down)" /> {t("legendOwed")}
        </li>
        <li className="flex items-center gap-1.5">
          <Swatch color="var(--diverge-up)" /> {t("legendOwes")}
        </li>
      </ul>
      <ul className="flex flex-col gap-4 sm:gap-3" aria-label={t("balancesAria")}>
        {rows.map((b) => {
          const you = b.user_id === me;
          const who = you ? t("youSubject") : name(b.user_id);
          const abs = b.balance.replace(/^-/, "");
          const owed = b.balance_minor > 0;
          const state = b.balance_minor === 0 ? "settled" : owed ? "owed" : "owes";
          // Bar length is drawing only; the amount next to it comes from the API string.
          const half = (Math.abs(b.balance_minor) / max) * 50;
          return (
            <li
              key={b.user_id}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 text-sm sm:grid-cols-[9.5rem_minmax(0,1fr)_8.5rem]"
            >
              <span className="flex min-w-0 items-center gap-2.5">
                <MemberAvatar house={house} userId={b.user_id} name={name(b.user_id)} size="sm" />
                <span className={`truncate ${you ? "font-semibold" : "font-medium"}`}>{who}</span>
              </span>
              <span className="text-right sm:col-start-3 sm:row-start-1">
                <span aria-hidden>
                  {b.balance_minor === 0 ? (
                    <span className="text-muted">{t("settled")}</span>
                  ) : (
                    <Money
                      amount={b.balance}
                      currency={cur}
                      signed
                      className={`font-semibold tabular-nums ${owed ? "text-positive" : "text-danger"}`}
                    />
                  )}
                </span>
                <span className="sr-only">{t("balanceSr", { you: you ? 1 : 0, state, amount: formatMoney(abs, cur) })}</span>
              </span>
              <span aria-hidden className="relative col-span-2 h-5 sm:col-span-1 sm:col-start-2 sm:row-start-1">
                <span className="absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 rounded-full bg-foreground/[0.04]" />
                <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-[var(--axis)]" />
                {b.balance_minor !== 0 && (
                  <span
                    className={`absolute top-1/2 h-2 -translate-y-1/2 ${owed ? "rounded-r-full bg-[var(--diverge-down)]" : "rounded-l-full bg-[var(--diverge-up)]"}`}
                    style={owed ? { left: "50%", width: `${half}%`, minWidth: 3 } : { right: "50%", width: `${half}%`, minWidth: 3 }}
                  />
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Suggested transfers as "A → B amount" cards, each with a one click "Record payment". */
export function SettleUpPanel({
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
  const t = useT(houseMessages);
  const c = useT(common);
  const [draft, setDraft] = useState<Draft | null>(null);
  const cur = balances.currency;

  return (
    <div className="flex flex-col gap-4">
      {balances.transfers.length === 0 ? (
        <Empty icon={<CircleCheck />}>{t("everyoneSettled")}</Empty>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {balances.transfers.map((tr, i) => {
            const sentence = t("willPay", {
              from: tr.from_user === me ? t("youSubject") : name(tr.from_user),
              to: tr.to_user === me ? t("youObject") : name(tr.to_user),
              fromMe: tr.from_user === me ? 1 : 0,
              toMe: tr.to_user === me ? 1 : 0,
            });
            const active = draft?.from_user === tr.from_user && draft.to_user === tr.to_user && draft.amount === tr.amount;
            return (
              <li
                key={i}
                className={`flex flex-col gap-3 rounded-xl border p-3.5 transition ${active ? "border-accent/50 bg-accent-soft" : "border-border"}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="flex min-w-0 items-center gap-2">
                    <MemberAvatar house={house} userId={tr.from_user} name={name(tr.from_user)} size="sm" />
                    <ArrowRight aria-hidden className="size-4 shrink-0 text-muted" />
                    <MemberAvatar house={house} userId={tr.to_user} name={name(tr.to_user)} size="sm" />
                    <span className="ml-1 min-w-0 truncate text-sm font-medium">{sentence}</span>
                  </span>
                  <Money amount={tr.amount} currency={cur} className="text-base font-semibold tabular-nums" />
                </div>
                <Button
                  size="sm"
                  variant={active ? "ghost" : "primary"}
                  className="self-start"
                  aria-label={active ? undefined : t("recordAria", { sentence })}
                  onClick={() => setDraft(active ? null : { from_user: tr.from_user, to_user: tr.to_user, amount: tr.amount })}
                >
                  <HandCoins aria-hidden className="size-3.5" />
                  {active ? c("close") : t("recordPayment")}
                </Button>
              </li>
            );
          })}
        </ul>
      )}

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

      {!draft && house.members.length > 1 && (
        <Button
          variant="subtle"
          size="sm"
          className="self-start"
          onClick={() => setDraft({ from_user: me, to_user: house.members.find((m) => m.user_id !== me)?.user_id ?? "", amount: "" })}
        >
          <Plus aria-hidden className="size-3.5" />
          {t("recordAnother")}
        </Button>
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
  const t = useT(houseMessages);
  const c = useT(common);
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
      setError(t("errAmount"));
      return;
    }
    if (from === to) {
      setError(t("errSamePerson"));
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
      notify(t("paymentRecorded"), "success");
      onSaved();
    } catch (err) {
      setConflict(err instanceof ApiError && err.status === 409);
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="flex flex-col gap-3 rounded-xl border border-border bg-background/60 p-4"
      aria-label={t("recordTitle")}
    >
      <div>
        <h3 className="text-sm font-semibold">{t("recordTitle")}</h3>
        <p className="mt-0.5 text-xs text-muted">{t("recordHint")}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <SelectField label={t("whoPaid")} name="from_user" defaultValue={draft.from_user}>
          {house.members.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.display_name}
              {m.user_id === me ? t("youTag") : ""}
            </option>
          ))}
        </SelectField>
        <SelectField label={t("whoGot")} name="to_user" defaultValue={draft.to_user}>
          {house.members.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.display_name}
              {m.user_id === me ? t("youTag") : ""}
            </option>
          ))}
        </SelectField>
        <Field
          label={t("amountIn", { currency: house.currency })}
          name="amount"
          defaultValue={draft.amount}
          required
          inputMode="decimal"
          autoComplete="off"
        />
        <Field label={t("noteOptional")} name="note" maxLength={500} placeholder={t("notePlaceholder")} />
      </div>
      {conflict && (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" name="allow_overpayment" className="mt-0.5 size-4 accent-[var(--accent)]" />
          {t("overpay")}
        </label>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? c("saving") : t("recordPayment")}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          {c("cancel")}
        </Button>
      </div>
      <ErrorText error={error} />
    </form>
  );
}

/** Recorded payments, newest first as the API sends them. */
export function PaymentHistory({
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
  const t = useT(houseMessages);
  const notify = useToast();
  const [confirm, setConfirm] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  async function undo(s: Settlement) {
    setBusy(true);
    try {
      await api.deleteSettlement(house.id, s.id);
      notify(t("undoneToast"), "success");
      setConfirm(null);
      onChanged();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  }

  if (settlements.length === 0) {
    return <Empty icon={<HandCoins />}>{t("noPayments")}</Empty>;
  }
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col divide-y divide-border text-sm">
        {settlements.map((s) => (
          <li key={s.id} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
            <div className="flex items-center justify-between gap-3">
              <span className="flex min-w-0 items-center gap-3">
                <span aria-hidden className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-foreground/[0.05]">
                  <HandCoins className="size-4 text-muted" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-medium">
                    {t("paid", {
                      from: s.from_user === me ? t("youSubject") : name(s.from_user),
                      to: s.to_user === me ? t("youObject") : name(s.to_user),
                      fromMe: s.from_user === me ? 1 : 0,
                      toMe: s.to_user === me ? 1 : 0,
                    })}
                  </span>
                  <span className="block text-xs text-muted">
                    {formatDateTime(s.created_at)} ·{" "}
                    {t("recordedBy", { who: s.created_by === me ? t("youObject") : name(s.created_by) })}
                    {s.note && ` · ${s.note}`}
                  </span>
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-1">
                <Money amount={s.amount} currency={s.currency} className="font-medium tabular-nums" />
                {s.created_by === me && confirm !== s.id && (
                  <button
                    type="button"
                    onClick={() => setConfirm(s.id)}
                    aria-label={t("undoAria", { amount: formatMoney(s.amount, s.currency) })}
                    title={t("undo")}
                    className="ml-1 inline-flex size-7 items-center justify-center rounded-md text-muted hover:bg-foreground/5 hover:text-foreground"
                  >
                    <Undo2 aria-hidden className="size-4" />
                  </button>
                )}
              </span>
            </div>
            {confirm === s.id && (
              <div className="flex flex-wrap items-center gap-2 pl-11">
                <span className="text-xs text-muted">{t("undoConfirm")}</span>
                <Button size="sm" variant="danger" onClick={() => undo(s)} disabled={busy}>
                  {t("undoPayment")}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>
                  {t("keep")}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">{t("onlyRecorder")}</p>
    </div>
  );
}
