"use client";

import { type FormEvent, useState } from "react";
import { api, type House, type SplitExpense, type SplitType } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { capitalize, formatMoney, fromMinor, normalizeAmount, percentToHundredths, toMinor } from "@/lib/format";
import { useWarningToasts, useToast } from "@/components/Toast";
import { Button, ErrorText, Field, SelectField, controlClass, errorMessage } from "@/components/ui";

const SPLITS: { value: SplitType; label: string; help: string }[] = [
  { value: "equal", label: "Equal", help: "Everyone chosen pays the same." },
  { value: "percent", label: "Percent", help: "Give each person a percent. They must add up to 100." },
  { value: "exact", label: "Exact", help: "Give each person an amount. They must add up to the total." },
  { value: "items", label: "Per item", help: "Each line is shared by the people ticked on it. No one ticked means everyone." },
];

type ItemRow = { key: number; description: string; amount: string; assignees: string[] };

/** "0" and "" count as zero in share fields; anything else must be a valid amount. */
function shareMinor(input: string): number | null {
  const s = input.trim();
  if (!s || /^0+([.,]0+)?$/.test(s)) return 0;
  const n = normalizeAmount(s);
  return n ? toMinor(n) : null;
}

export function SplitExpenseForm({ house, me, onSaved }: { house: House; me: string; onSaved: () => void }) {
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
        ? { ok: false, text: "Pick at least one person." }
        : { ok: true, text: `Split between ${participants.length} ${participants.length === 1 ? "person" : "people"}.` };
  } else if (splitType === "percent") {
    const values = memberIds.map((id) => percentToHundredths(percents[id] ?? ""));
    if (values.some((v) => v === null)) check = { ok: false, text: "Percents are numbers from 0 to 100 with up to 2 decimals." };
    else {
      const sum = values.reduce<number>((a, v) => a + (v ?? 0), 0);
      const left = 10000 - sum;
      const pct = (h: number) => fromMinor(h).replace(/\.00$/, "");
      check =
        left === 0
          ? { ok: true, text: "Adds up to 100%." }
          : left > 0
            ? { ok: false, text: `${pct(sum)}% given, ${pct(left)}% left to assign.` }
            : { ok: false, text: `${pct(sum)}% given, ${pct(-left)}% too much.` };
    }
  } else if (splitType === "exact") {
    const values = memberIds.map((id) => shareMinor(amounts[id] ?? ""));
    if (values.some((v) => v === null)) check = { ok: false, text: "Amounts look like 120 or 120,50." };
    else if (totalMinor === null) check = { ok: false, text: "Enter the total first." };
    else {
      const sum = values.reduce<number>((a, v) => a + (v ?? 0), 0);
      const left = totalMinor - sum;
      check =
        left === 0
          ? { ok: true, text: "Adds up to the total." }
          : left > 0
            ? { ok: false, text: `${money(sum)} assigned, ${money(left)} left.` }
            : { ok: false, text: `${money(sum)} assigned, ${money(-left)} more than the total.` };
    }
  } else {
    const filled = items.filter((r) => r.description.trim() || r.amount.trim());
    const values = filled.map((r) => (r.description.trim() ? normalizeAmount(r.amount) : null));
    if (filled.length === 0) check = { ok: false, text: "Add at least one line." };
    else if (values.some((v) => v === null)) check = { ok: false, text: "Every line needs a description and an amount." };
    else if (totalMinor !== null) {
      const sum = values.reduce<number>((a, v) => a + toMinor(v as string), 0);
      const diff = totalMinor - sum;
      check =
        diff === 0
          ? { ok: true, text: "Lines add up to the total." }
          : {
              ok: true,
              text: `Lines add up to ${money(sum)}. The ${diff > 0 ? "extra" : "discount of"} ${money(Math.abs(diff))} is shared in proportion to what each person had.`,
            };
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
      setError("Enter the total, like 600 or 600,50.");
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
      notify(`Added ${saved.merchant}.`, "success");
      toastWarnings(saved.warnings);
      form.reset();
      setTotal("");
      setPercents({});
      setAmounts({});
      setItems([{ key: nextKey, description: "", amount: "", assignees: [] }]);
      setNextKey((k) => k + 1);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const defaultPayer = memberIds.includes(me) ? me : memberIds[0];

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <fieldset>
        <legend className="mb-2 text-sm text-muted">How to split</legend>
        <div className="grid grid-cols-2 gap-1 rounded-lg border border-border p-1 sm:grid-cols-4">
          {SPLITS.map((s) => (
            <label
              key={s.value}
              className={`flex h-9 cursor-pointer items-center justify-center rounded-md text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-[var(--accent)] ${
                splitType === s.value ? "bg-accent text-accent-foreground font-medium" : "hover:bg-foreground/5"
              }`}
            >
              <input
                type="radio"
                name="split_type"
                value={s.value}
                checked={splitType === s.value}
                onChange={() => {
                  setSplitType(s.value);
                  setError(null);
                }}
                className="sr-only"
              />
              {s.label}
            </label>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted">{SPLITS.find((s) => s.value === splitType)?.help}</p>
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="What" name="merchant" required maxLength={200} placeholder="Electricity bill" className="sm:col-span-2" />
        <div className="grid grid-cols-[1fr_96px] gap-3">
          <Field
            label="Total"
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
            <Field label="Currency" value={house.currency} readOnly aria-readonly />
          ) : (
            <SelectField label="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)}>
              {[house.currency, ...["TRY", "USD", "EUR", "GBP"].filter((c) => c !== house.currency)].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </SelectField>
          )}
        </div>
        <SelectField label="Paid by" name="paid_by" defaultValue={defaultPayer}>
          {members.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.display_name}
              {m.user_id === me ? " (you)" : ""}
            </option>
          ))}
        </SelectField>
        <Field label="Date" name="expense_date" type="date" hint="Empty means today." />
        <SelectField label="Category" name="category" defaultValue="">
          <option value="">Let Kasa decide</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {capitalize(c)}
            </option>
          ))}
        </SelectField>
      </div>
      {splitType === "exact" && (
        <p className="-mt-2 text-xs text-muted">Exact amounts are in the house currency ({house.currency}).</p>
      )}
      {splitType !== "exact" && currency !== house.currency && (
        <p className="-mt-2 text-xs text-muted">Kasa converts this to {house.currency} at the TCMB rate for the date.</p>
      )}

      {splitType === "equal" && (
        <fieldset>
          <legend className="mb-2 text-sm text-muted">Who shares it</legend>
          <div className="flex flex-wrap gap-2">
            {members.map((m) => (
              <label
                key={m.user_id}
                className="flex items-center gap-2 rounded-full border border-border px-3 py-1.5 text-sm has-[:checked]:border-accent has-[:checked]:bg-accent/10"
              >
                <input
                  type="checkbox"
                  checked={participants.includes(m.user_id)}
                  onChange={() => setParticipants((p) => toggle(p, m.user_id))}
                  className="size-4 accent-[var(--accent)]"
                />
                {m.display_name}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {(splitType === "percent" || splitType === "exact") && (
        <fieldset>
          <legend className="mb-2 text-sm text-muted">{splitType === "percent" ? "Percent per person" : "Amount per person"}</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {members.map((m) => {
              const id = `split-${splitType}-${m.user_id}`;
              const values = splitType === "percent" ? percents : amounts;
              const setValues = splitType === "percent" ? setPercents : setAmounts;
              const bad =
                splitType === "percent"
                  ? percentToHundredths(values[m.user_id] ?? "") === null
                  : shareMinor(values[m.user_id] ?? "") === null;
              return (
                <div key={m.user_id} className="grid grid-cols-[1fr_8rem] items-center gap-2 text-sm">
                  <label htmlFor={id} className="truncate">
                    {m.display_name}
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
                      className={`${controlClass} pr-9 text-right`}
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
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-2 text-sm text-muted">Lines</legend>
          {items.map((row, index) => (
            <div key={row.key} className="flex flex-col gap-2 rounded-lg border border-border p-3">
              <div className="grid grid-cols-[1fr_7rem_auto] items-end gap-2">
                <Field
                  label={`Line ${index + 1}`}
                  value={row.description}
                  placeholder="Cheese"
                  maxLength={200}
                  onChange={(e) =>
                    setItems((rows) => rows.map((r) => (r.key === row.key ? { ...r, description: e.target.value } : r)))
                  }
                />
                <Field
                  label="Amount"
                  inputMode="decimal"
                  autoComplete="off"
                  placeholder="60,00"
                  value={row.amount}
                  onChange={(e) => setItems((rows) => rows.map((r) => (r.key === row.key ? { ...r, amount: e.target.value } : r)))}
                />
                <Button
                  variant="ghost"
                  onClick={() => setItems((rows) => rows.filter((r) => r.key !== row.key))}
                  disabled={items.length === 1}
                  aria-label={`Remove line ${index + 1}`}
                >
                  ×
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm" role="group" aria-label={`Who had line ${index + 1}`}>
                <span className="text-xs text-muted">Shared by</span>
                {members.map((m) => (
                  <label key={m.user_id} className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={row.assignees.includes(m.user_id)}
                      onChange={() =>
                        setItems((rows) =>
                          rows.map((r) => (r.key === row.key ? { ...r, assignees: toggle(r.assignees, m.user_id) } : r)),
                        )
                      }
                      className="size-4 accent-[var(--accent)]"
                    />
                    {m.display_name}
                  </label>
                ))}
                {row.assignees.length === 0 && <span className="text-xs text-muted">(everyone)</span>}
              </div>
            </div>
          ))}
          <Button
            variant="ghost"
            className="self-start"
            onClick={() => {
              setItems((rows) => [...rows, { key: nextKey, description: "", amount: "", assignees: [] }]);
              setNextKey((k) => k + 1);
            }}
          >
            Add a line
          </Button>
        </fieldset>
      )}

      <Field label="Note (optional)" name="note" maxLength={500} />

      <p aria-live="polite" className={`text-sm ${check.ok ? "text-muted" : "text-warning"}`}>
        {check.text}
      </p>

      <Button type="submit" disabled={saving || members.length === 0}>
        {saving ? "Saving" : "Add shared expense"}
      </Button>
      <ErrorText error={error} />
      <p className="text-xs text-muted">Kasa works out the exact shares. They always add up to the total.</p>
    </form>
  );
}
