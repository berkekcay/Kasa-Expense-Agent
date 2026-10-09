"use client";

import { type FormEvent, useEffect, useState } from "react";
import { api, type Balances, type Expense, type House } from "@/lib/api";
import { useUserId } from "@/lib/user";
import { Button, Card, ErrorText, Field, Money, errorMessage } from "@/components/ui";
import { ExpenseList } from "@/features/expenses/ExpenseList";

export function HouseView() {
  const userId = useUserId();
  const [houses, setHouses] = useState<House[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const refresh = () => setReload((n) => n + 1);

  useEffect(() => {
    let cancelled = false;
    api
      .listHouses()
      .then((data) => {
        if (!cancelled) setHouses(data);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e));
      });
    return () => {
      cancelled = true;
    };
  }, [userId, reload]);

  const house = houses?.find((h) => h.id === selectedId) ?? houses?.[0] ?? null;

  async function createHouse(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setError(null);
    try {
      const created = await api.createHouse(String(new FormData(form).get("name")));
      form.reset();
      setSelectedId(created.id);
      refresh();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
      <div className="flex flex-col gap-6">
        <Card title="Your houses">
          {houses === null ? (
            <p className="text-sm text-muted">Loading…</p>
          ) : houses.length === 0 ? (
            <p className="text-sm text-muted">No house yet — create one below.</p>
          ) : (
            <ul className="flex flex-col gap-1 text-sm">
              {houses.map((h) => (
                <li key={h.id}>
                  <button
                    onClick={() => setSelectedId(h.id)}
                    className={`w-full rounded-md px-3 py-2 text-left ${h.id === house?.id ? "bg-accent/15 font-medium text-accent" : "hover:bg-foreground/5"}`}
                  >
                    {h.name} <span className="text-muted">· {h.members.length}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="New house">
          <form onSubmit={createHouse} className="flex flex-col gap-3">
            <Field label="Name" name="name" required maxLength={100} placeholder="Moda flat" />
            <Button type="submit">Create</Button>
          </form>
          <ErrorText error={error} />
        </Card>
      </div>

      {house ? (
        <HouseDetail key={`${house.id}-${userId}`} house={house} onChanged={refresh} reload={reload} />
      ) : (
        <Card>
          <p className="text-sm text-muted">Create a house to start splitting bills with flatmates.</p>
        </Card>
      )}
    </div>
  );
}

function HouseDetail({ house, onChanged, reload }: { house: House; onChanged: () => void; reload: number }) {
  const userId = useUserId();
  const [balances, setBalances] = useState<Balances | null>(null);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.balances(house.id), api.listHouseExpenses(house.id)])
      .then(([b, e]) => {
        if (cancelled) return;
        setBalances(b);
        setExpenses(e);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e));
      });
    return () => {
      cancelled = true;
    };
  }, [house.id, reload]);

  async function submit(e: FormEvent<HTMLFormElement>, action: (data: FormData) => Promise<unknown>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    setError(null);
    try {
      await action(new FormData(form));
      form.reset();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const name = (id: string) => house.members.find((m) => m.user_id === id)?.display_name ?? id;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 md:grid-cols-2">
        <Card title={`${house.name} · members`}>
          <ul className="mb-4 flex flex-wrap gap-2 text-sm">
            {house.members.map((m) => (
              <li key={m.user_id} className="rounded-full border border-border px-3 py-1">
                {m.display_name}
                {m.user_id !== m.display_name && <span className="text-muted"> ({m.user_id})</span>}
              </li>
            ))}
          </ul>
          <form
            onSubmit={(e) =>
              submit(e, (d) => api.addMember(house.id, String(d.get("user_id")), String(d.get("display_name"))))
            }
            className="grid grid-cols-2 gap-3"
          >
            <Field label="User id" name="user_id" required placeholder="ayse" />
            <Field label="Display name" name="display_name" placeholder="Ayşe" />
            <Button type="submit" variant="ghost" disabled={busy} className="col-span-2">
              Add member
            </Button>
          </form>
        </Card>

        <Card title="Add shared expense (equal split)">
          <form
            onSubmit={(e) =>
              submit(e, (d) =>
                api.addHouseExpense(house.id, {
                  merchant: String(d.get("merchant")),
                  total: String(d.get("total")).replace(",", "."),
                  paid_by: String(d.get("paid_by")) || undefined,
                  expense_date: String(d.get("expense_date")) || undefined,
                }),
              )
            }
            className="grid grid-cols-2 gap-3"
          >
            <Field label="What" name="merchant" required placeholder="Electricity" className="col-span-2" />
            <Field label={`Total (${house.currency})`} name="total" required inputMode="decimal" pattern="\d+([.,]\d{1,2})?" />
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted">Paid by</span>
              <select name="paid_by" defaultValue={userId} className="h-9 rounded-lg border border-border bg-background px-2">
                {house.members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.display_name}
                  </option>
                ))}
              </select>
            </label>
            <Field label="Date" name="expense_date" type="date" className="col-span-2" />
            <Button type="submit" disabled={busy} className="col-span-2">
              Split equally between {house.members.length}
            </Button>
          </form>
        </Card>
      </div>
      <ErrorText error={error} />

      <Card title="Balances & settle up">
        {!balances ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : (
          <div className="grid gap-6 md:grid-cols-2">
            <ul className="flex flex-col gap-1 text-sm">
              {balances.balances.map((b) => (
                <li key={b.user_id} className="flex justify-between gap-4">
                  <span>{name(b.user_id)}</span>
                  <span
                    className={`tabular-nums ${b.balance_minor > 0 ? "text-positive" : b.balance_minor < 0 ? "text-danger" : "text-muted"}`}
                  >
                    {b.balance_minor > 0 ? "+" : ""}
                    {b.balance} {balances.currency}
                  </span>
                </li>
              ))}
            </ul>
            <div className="text-sm">
              {balances.transfers.length === 0 ? (
                <p className="text-muted">All settled up.</p>
              ) : (
                <ul className="flex flex-col gap-1">
                  {balances.transfers.map((t, i) => (
                    <li key={i}>
                      <strong>{name(t.from_user)}</strong> pays <strong>{name(t.to_user)}</strong>{" "}
                      <Money amount={t.amount} currency={balances.currency} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </Card>

      <Card title="House expenses">
        <ExpenseList expenses={expenses} empty="No shared expenses yet." />
      </Card>
    </div>
  );
}
