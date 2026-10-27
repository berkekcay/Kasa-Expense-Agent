"use client";

import { Check, CircleAlert, CircleCheck, Plus, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api, type House, type SplitExpense, type SplitType } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { categoryLabel, common } from "@/lib/commonMessages";
import { formatMoney, fromMinor, normalizeAmount, percentToHundredths, toMinor } from "@/lib/format";
import { useLocale, useT } from "@/lib/i18n";
import { useWarningToasts, useToast } from "@/components/Toast";
import { DatePicker } from "@/components/pickers";
import { Button, ErrorText, Field, Segmented, SelectField, controlClass, errorMessage } from "@/components/ui";
import { houseMessages } from "./messages";
import { MemberAvatar } from "./parts";

const SPLITS: SplitType[] = ["equal", "percent", "exact", "items"];

type ItemRow = { key: number; description: string; amount: string; assignees: string[] };

/** "0" and "" count as zero in share fields; anything else must be a valid amount. */
function shareMinor(input: string): number | null {
  const s = input.trim();
  if (!s || /^0+([.,]0+)?$/.test(s)) return 0;
  const n = normalizeAmount(s);
  return n ? toMinor(n) : null;
}

export function SplitExpenseForm({ house, me, onSaved }: { house: House; me: string; onSaved: () => void }) {
  const t = useT(houseMessages);
  const c = useT(common);
  const locale = useLocale();
  const notify = useToast();
  const toastWarnings = useWarningToasts();
  const members = house.members;
  const memberIds = members.map((m) => m.user_id);
  const [splitType, setSplitType] = useState<SplitType>("equal");
  const [total, setTotal] = useState("");
  const [currency, setCurrency] = useState(house.currency);
  const [participants, setParticipants] = useState<string[]>(memberIds);
  const [percents, setPercents] = useState<Record<string, string>>({});
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [items, setItems] = useState<ItemRow[]>([{ key: 1, description: "", amount: "", assignees: [] }]);
  const [nextKey, setNextKey] = useState(2);
  const [formKey, setFormKey] = useState(0); // remounts the form (and its DatePicker) after a save
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalNorm = normalizeAmount(total);
  const totalMinor = totalNorm ? toMinor(totalNorm) : null;
  const shownCurrency = splitType === "exact" ? house.currency : currency;
  const money = (minor: number) => formatMoney(fromMinor(minor), shownCurrency);

  // Live checks. They guide the form; the API does the real split and has the last word.
  let check: { ok: boolean; text: string } = { ok: true, text: "" };
  if (splitType === "equal") {
    check =
      participants.length === 0
        ? { ok: false, text: t("pickOne") }
        : { ok: true, text: t("splitBetween", { n: participants.length }) };
  } else if (splitType === "percent") {
    const values = memberIds.map((id) => percentToHundredths(percents[id] ?? ""));
    if (values.some((v) => v === null)) check = { ok: false, text: t("percentFormat") };
    else {
      const sum = values.reduce<number>((a, v) => a + (v ?? 0), 0);
      const left = 10000 - sum;
      const pct = (h: number) => {
        const v = fromMinor(h).replace(/\.00$/, "");
        return locale === "tr" ? v.replace(".", ",") : v;
      };
      check =
        left === 0
          ? { ok: true, text: t("adds100") }
          : left > 0
            ? { ok: false, text: t("pctLeft", { given: pct(sum), left: pct(left) }) }
            : { ok: false, text: t("pctOver", { given: pct(sum), over: pct(-left) }) };
    }
  } else if (splitType === "exact") {
    const values = memberIds.map((id) => shareMinor(amounts[id] ?? ""));
    if (values.some((v) => v === null)) check = { ok: false, text: t("amountFormat") };
    else if (totalMinor === null) check = { ok: false, text: t("totalFirst") };
    else {
      const sum = values.reduce<number>((a, v) => a + (v ?? 0), 0);
      const left = totalMinor - sum;
      check =
        left === 0
          ? { ok: true, text: t("addsTotal") }
          : left > 0
            ? { ok: false, text: t("amountLeft", { sum: money(sum), left: money(left) }) }
            : { ok: false, text: t("amountOver", { sum: money(sum), over: money(-left) }) };
    }
  } else {
    const filled = items.filter((r) => r.description.trim() || r.amount.trim());
    const values = filled.map((r) => (r.description.trim() ? normalizeAmount(r.amount) : null));
    if (filled.length === 0) check = { ok: false, text: t("addLineCheck") };
    else if (values.some((v) => v === null)) check = { ok: false, text: t("lineNeeds") };
    else if (totalMinor !== null) {
      const sum = values.reduce<number>((a, v) => a + toMinor(v as string), 0);
      const diff = totalMinor - sum;
      check =
        diff === 0
          ? { ok: true, text: t("linesTotal") }
          : { ok: true, text: t("linesDiff", { sum: money(sum), diff: money(Math.abs(diff)), extra: diff > 0 ? 1 : 0 }) };
    }
  }

  function toggle(list: string[], id: string): string[] {
    return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    if (!totalNorm) {
      setError(t("errTotal"));
      return;
    }
    if (!check.ok) {
      setError(check.text);
      return;
    }
    const base = {
      merchant: String(data.get("merchant")).trim(),
      total: totalNorm,
      expense_date: String(data.get("expense_date")) || undefined,
      category: String(data.get("category")) || undefined,
      note: String(data.get("note") ?? "").trim() || undefined,
      paid_by: String(data.get("paid_by")) || undefined,
      currency: splitType === "exact" ? undefined : currency,
    };
    let body: SplitExpense;
    if (splitType === "equal") {
      body = {
        ...base,
        split_type: "equal",
        participants: participants.length === memberIds.length ? undefined : participants,
      };
    } else if (splitType === "percent") {
      const entries = memberIds
        .filter((id) => (percentToHundredths(percents[id] ?? "") ?? 0) > 0)
        .map((id) => [id, (percents[id] ?? "").trim().replace(",", ".")]);
      body = { ...base, split_type: "percent", percents: Object.fromEntries(entries) };
    } else if (splitType === "exact") {
      const entries = memberIds
        .filter((id) => (shareMinor(amounts[id] ?? "") ?? 0) > 0)
        .map((id) => [id, fromMinor(shareMinor(amounts[id] ?? "") ?? 0)]);
      body = { ...base, split_type: "exact", amounts: Object.fromEntries(entries) };
    } else {
      body = {
        ...base,
        split_type: "items",
        items: items
          .filter((r) => r.description.trim())
          .map((r) => ({ description: r.description.trim(), amount: normalizeAmount(r.amount) as string, assignees: r.assignees })),
      };
    }

    setSaving(true);
    setError(null);
    try {
      const saved = await api.addSplitExpense(house.id, body);
      notify(t("addedExpense", { merchant: saved.merchant }), "success");
      toastWarnings(saved.warnings);
      form.reset();
      setTotal("");
      setPercents({});
      setAmounts({});
      setItems([{ key: nextKey, description: "", amount: "", assignees: [] }]);
      setNextKey((k) => k + 1);
      setFormKey((k) => k + 1);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const defaultPayer = memberIds.includes(me) ? me : memberIds[0];

  return (
    <form key={formKey} onSubmit={onSubmit} className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <span className="text-sm text-muted">{t("howToSplit")}</span>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <Segmented
            label={t("howToSplit")}
            value={splitType}
            options={SPLITS.map((s) => ({ value: s, label: t(`splitLabel.${s}`) }))}
            onChange={(v) => {
              setSplitType(v);
              setError(null);
            }}
          />
          <p className="text-xs text-muted">{t(`splitHelp.${splitType}`)}</p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("what")} name="merchant" required maxLength={200} placeholder={t("whatPlaceholder")} className="sm:col-span-2" />
        <div className="grid grid-cols-[minmax(0,1fr)_6rem] gap-3">
          <Field
            label={c("total")}
            name="total"
            required
            inputMode="decimal"
            autoComplete="off"
            placeholder="600,00"
            value={total}
            onChange={(e) => setTotal(e.target.value)}
            aria-invalid={total !== "" && !totalNorm}
          />
          {splitType === "exact" ? (
            <Field label={t("currency")} value={house.currency} readOnly aria-readonly />
          ) : (
            <SelectField label={t("currency")} value={currency} onChange={(e) => setCurrency(e.target.value)}>
              {[house.currency, ...["TRY", "USD", "EUR", "GBP"].filter((x) => x !== house.currency)].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </SelectField>
          )}
        </div>
        <SelectField label={t("paidByLabel")} name="paid_by" defaultValue={defaultPayer}>
          {members.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.display_name}
              {m.user_id === me ? t("youTag") : ""}
            </option>
          ))}
        </SelectField>
        <DatePicker label={t("date")} name="expense_date" hint={t("dateHint")} placeholder={c("today")} />
        <SelectField label={t("category")} name="category" defaultValue="">
          <option value="">{t("letKasa")}</option>
          {CATEGORIES.map((cat) => (
            <option key={cat} value={cat}>
              {categoryLabel(cat)}
            </option>
          ))}
        </SelectField>
        {(splitType === "exact" || currency !== house.currency) && (
          <p className="text-xs text-muted sm:col-span-2">
            {splitType === "exact"
              ? t("exactCurrency", { currency: house.currency })
              : t("converts", { currency: house.currency })}
          </p>
        )}
      </div>

      {splitType === "equal" && (
        <fieldset>
          <legend className="mb-2 text-sm text-muted">{t("whoShares")}</legend>
          <div className="flex flex-wrap gap-2">
            {members.map((m) => {
              const on = participants.includes(m.user_id);
              return (
                <label
                  key={m.user_id}
                  className={`flex cursor-pointer items-center gap-2 rounded-full border py-1 pr-3 pl-1 text-sm transition has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--accent)] ${
                    on ? "border-accent/50 bg-accent-soft" : "border-border text-muted hover:border-border-strong"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => setParticipants((p) => toggle(p, m.user_id))}
                    className="sr-only"
                  />
                  <MemberAvatar house={house} userId={m.user_id} name={m.display_name} size="sm" />
                  <span className={on ? "font-medium text-foreground" : ""}>
                    {m.display_name}
                    {m.user_id === me && <span className="font-normal text-muted">{t("youTag")}</span>}
                  </span>
                  {on && <Check aria-hidden className="size-3.5 text-accent" />}
                </label>
              );
            })}
          </div>
        </fieldset>
      )}

      {(splitType === "percent" || splitType === "exact") && (
        <fieldset>
          <legend className="mb-2 text-sm text-muted">{splitType === "percent" ? t("percentPer") : t("amountPer")}</legend>
          <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            {members.map((m) => {
              const id = `split-${splitType}-${m.user_id}`;
              const values = splitType === "percent" ? percents : amounts;
              const setValues = splitType === "percent" ? setPercents : setAmounts;
              const bad =
                splitType === "percent"
                  ? percentToHundredths(values[m.user_id] ?? "") === null
                  : shareMinor(values[m.user_id] ?? "") === null;
              return (
                <div key={m.user_id} className="grid grid-cols-[minmax(0,1fr)_8.5rem] items-center gap-2 text-sm">
                  <label htmlFor={id} className="flex min-w-0 items-center gap-2">
                    <MemberAvatar house={house} userId={m.user_id} name={m.display_name} size="sm" />
                    <span className="truncate">{m.display_name}</span>
                  </label>
                  <div className="relative">
                    <input
                      id={id}
                      inputMode="decimal"
                      autoComplete="off"
                      placeholder="0"
                      value={values[m.user_id] ?? ""}
                      onChange={(e) => setValues((v) => ({ ...v, [m.user_id]: e.target.value }))}
                      aria-invalid={bad}
                      className={`${controlClass} pr-11 text-right tabular-nums`}
                    />
                    <span aria-hidden className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-muted">
                      {splitType === "percent" ? "%" : house.currency}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </fieldset>
      )}

      {splitType === "items" && (
        <fieldset className="flex flex-col gap-2.5">
          <legend className="mb-2 text-sm text-muted">{t("lines")}</legend>
          {items.map((row, index) => (
            <div key={row.key} className="flex flex-col gap-3 rounded-xl border border-border p-3">
              <div className="grid grid-cols-[minmax(0,1fr)_7rem_auto] items-end gap-2">
                <Field
                  label={t("lineN", { n: index + 1 })}
                  value={row.description}
                  placeholder={t("linePlaceholder")}
                  maxLength={200}
                  onChange={(e) =>
                    setItems((rows) => rows.map((r) => (r.key === row.key ? { ...r, description: e.target.value } : r)))
                  }
                />
                <Field
                  label={t("amount")}
                  inputMode="decimal"
                  autoComplete="off"
                  placeholder="60,00"
                  value={row.amount}
                  onChange={(e) => setItems((rows) => rows.map((r) => (r.key === row.key ? { ...r, amount: e.target.value } : r)))}
                />
                <button
                  type="button"
                  onClick={() => setItems((rows) => rows.filter((r) => r.key !== row.key))}
                  disabled={items.length === 1}
                  aria-label={t("removeLine", { n: index + 1 })}
                  className="inline-flex size-9 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 hover:text-foreground disabled:pointer-events-none disabled:opacity-30"
                >
                  <X aria-hidden className="size-4" />
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 text-sm" role="group" aria-label={t("whoHadLine", { n: index + 1 })}>
                <span className="mr-1 text-xs text-muted">{t("sharedBy")}</span>
                {members.map((m) => {
                  const on = row.assignees.includes(m.user_id);
                  return (
                    <label
                      key={m.user_id}
                      className={`flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs transition has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--accent)] ${
                        on ? "border-accent/50 bg-accent-soft font-medium text-foreground" : "border-border text-muted hover:border-border-strong"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={on}
                        onChange={() =>
                          setItems((rows) =>
                            rows.map((r) => (r.key === row.key ? { ...r, assignees: toggle(r.assignees, m.user_id) } : r)),
                          )
                        }
                        className="sr-only"
                      />
                      {on && <Check aria-hidden className="size-3 text-accent" />}
                      {m.display_name}
                    </label>
                  );
                })}
                {row.assignees.length === 0 && <span className="text-xs text-muted">{t("everyone")}</span>}
              </div>
            </div>
          ))}
          <Button
            variant="subtle"
            size="sm"
            className="self-start"
            onClick={() => {
              setItems((rows) => [...rows, { key: nextKey, description: "", amount: "", assignees: [] }]);
              setNextKey((k) => k + 1);
            }}
          >
            <Plus aria-hidden className="size-3.5" />
            {t("addLine")}
          </Button>
        </fieldset>
      )}

      <Field label={t("noteOptional")} name="note" maxLength={500} />

      <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p aria-live="polite" className={`flex min-h-5 items-start gap-2 text-sm ${check.ok ? "text-muted" : "text-warning"}`}>
          {check.text &&
            (check.ok ? (
              <CircleCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-positive" />
            ) : (
              <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
            ))}
          <span>{check.text}</span>
        </p>
        <Button type="submit" disabled={saving || members.length === 0} className="shrink-0">
          {saving ? c("saving") : t("submitExpense")}
        </Button>
      </div>
      <ErrorText error={error} />
    </form>
  );
}
