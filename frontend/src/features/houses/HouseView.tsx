"use client";

import { type FormEvent, type KeyboardEvent, useState } from "react";
import { api, type House } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useUserId } from "@/lib/user";
import { useToast } from "@/components/Toast";
import { Async, Button, Card, Empty, ErrorText, Field, SelectField, errorMessage } from "@/components/ui";
import { ExpenseList } from "@/features/expenses/ExpenseList";
import { RemindersPanel } from "./Reminders";
import { BalancesPanel, SettlementsPanel } from "./SettleUp";
import { SplitExpenseForm } from "./SplitExpenseForm";

export function HouseView() {
  const userId = useUserId();
  const houses = useApi(() => api.listHouses(), []);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const list = houses.data ?? [];
  const house = list.find((h) => h.id === selectedId) ?? list[0] ?? null;

  return (
    // Phones: house list, then the selected house, then "New house". Desktop: list and form on the left.
    <div className="grid items-start gap-6 lg:grid-cols-[260px_1fr] lg:grid-rows-[auto_1fr]">
      <Card title="Your houses" className="lg:col-start-1 lg:row-start-1">
        <Async {...houses} label="Loading houses">
          {(rows) =>
            rows.length === 0 ? (
              <Empty>No house yet. Create one below.</Empty>
            ) : (
              <ul className="flex flex-col gap-1 text-sm">
                {rows.map((h) => (
                  <li key={h.id}>
                    <button
                      type="button"
                      aria-current={h.id === house?.id ? "true" : undefined}
                      onClick={() => setSelectedId(h.id)}
                      className={`w-full rounded-md px-3 py-2 text-left ${h.id === house?.id ? "bg-accent/15 font-medium text-accent" : "hover:bg-foreground/5"}`}
                    >
                      {h.name}{" "}
                      <span className="text-muted">
                        · {h.members.length} {h.members.length === 1 ? "member" : "members"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )
          }
        </Async>
      </Card>

      <div className="min-w-0 lg:col-start-2 lg:row-span-2 lg:row-start-1">
        {house ? (
          <HouseDetail key={`${house.id}-${userId}`} house={house} me={userId} onHouseChanged={houses.reload} />
        ) : (
          houses.data && (
            <Card>
              <Empty>Create a house to start splitting bills with flatmates.</Empty>
            </Card>
          )
        )}
      </div>

      <div className="lg:col-start-1 lg:row-start-2">
        <CreateHouse
          onCreated={(h) => {
            setSelectedId(h.id);
            houses.reload();
          }}
        />
      </div>
    </div>
  );
}

function CreateHouse({ onCreated }: { onCreated: (h: House) => void }) {
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const d = new FormData(form);
    setSaving(true);
    setError(null);
    try {
      const created = await api.createHouse(String(d.get("name")).trim(), String(d.get("currency")) || "TRY");
      form.reset();
      onCreated(created);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="New house">
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <Field label="Name" name="name" required maxLength={100} placeholder="Moda flat" />
        <SelectField label="Currency" name="currency" defaultValue="TRY">
          {["TRY", "EUR", "USD", "GBP"].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </SelectField>
        <Button type="submit" disabled={saving}>
          {saving ? "Creating" : "Create house"}
        </Button>
        <ErrorText error={error} />
      </form>
    </Card>
  );
}

const TABS = [
  { id: "balances", label: "Balances" },
  { id: "add", label: "Add expense" },
  { id: "expenses", label: "Expenses" },
  { id: "payments", label: "Payments" },
  { id: "reminders", label: "Reminders" },
  { id: "members", label: "Members" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function HouseDetail({ house, me, onHouseChanged }: { house: House; me: string; onHouseChanged: () => void }) {
  const [tab, setTab] = useState<TabId>("balances");
  const [version, setVersion] = useState(0);
  const refresh = () => setVersion((v) => v + 1);
  const balances = useApi(() => api.balances(house.id), [house.id, version]);
  const expenses = useApi(() => api.listHouseExpenses(house.id), [house.id, version]);
  const settlements = useApi(() => api.listSettlements(house.id), [house.id, version]);
  const reminders = useApi(() => api.listReminders(house.id), [house.id, version]);
  const google = useApi(() => api.integrations.googleStatus(), []);
  const name = (id: string) => house.members.find((m) => m.user_id === id)?.display_name ?? id;

  function onTabKey(e: KeyboardEvent<HTMLDivElement>) {
    const i = TABS.findIndex((t) => t.id === tab);
    let next = -1;
    if (e.key === "ArrowRight") next = (i + 1) % TABS.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + TABS.length) % TABS.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = TABS.length - 1;
    if (next < 0) return;
    e.preventDefault();
    setTab(TABS[next].id);
    document.getElementById(`house-tab-${TABS[next].id}`)?.focus();
  }

  return (
    <Card className="min-w-0">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">{house.name}</h2>
        <p className="text-sm text-muted">
          {house.members.map((m) => (m.user_id === me ? "You" : m.display_name)).join(", ")} · {house.currency}
        </p>
      </div>
      <div role="tablist" aria-label="House sections" onKeyDown={onTabKey} className="mb-5 flex flex-wrap gap-1 border-b border-border pb-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            id={`house-tab-${t.id}`}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            aria-controls={`house-panel-${t.id}`}
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => setTab(t.id)}
            className={`h-9 rounded-md px-3 text-sm ${tab === t.id ? "bg-accent/15 font-medium text-accent" : "text-muted hover:bg-foreground/5 hover:text-foreground"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`house-panel-${tab}`} aria-labelledby={`house-tab-${tab}`} tabIndex={0} className="outline-none">
        {tab === "balances" && (
          <Async {...balances} label="Loading balances">
            {(b) => <BalancesPanel house={house} balances={b} me={me} name={name} onChanged={refresh} />}
          </Async>
        )}
        {tab === "add" && (
          <SplitExpenseForm
            house={house}
            me={me}
            onSaved={() => {
              refresh();
            }}
          />
        )}
        {tab === "expenses" && (
          <Async {...expenses} label="Loading expenses">
            {(rows) => <ExpenseList expenses={rows} empty="No shared expenses yet." memberName={(id) => (id === me ? "you" : name(id))} />}
          </Async>
        )}
        {tab === "payments" && (
          <Async {...settlements} label="Loading payments">
            {(rows) => <SettlementsPanel house={house} settlements={rows} me={me} name={name} onChanged={refresh} />}
          </Async>
        )}
        {tab === "reminders" && (
          <Async {...reminders} label="Loading reminders">
            {(rows) => (
              <RemindersPanel
                house={house}
                reminders={rows}
                google={google.data}
                hasTransfers={(balances.data?.transfers.length ?? 0) > 0}
                me={me}
                name={name}
                onChanged={refresh}
              />
            )}
          </Async>
        )}
        {tab === "members" && <Members house={house} me={me} onChanged={onHouseChanged} />}
      </div>
    </Card>
  );
}

function Members({ house, me, onChanged }: { house: House; me: string; onChanged: () => void }) {
  const notify = useToast();
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const d = new FormData(form);
    setSaving(true);
    setError(null);
    try {
      const userId = String(d.get("user_id")).trim();
      await api.addMember(house.id, userId, String(d.get("display_name") ?? "").trim());
      notify(`Added ${userId}.`, "success");
      form.reset();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <ul className="flex flex-col divide-y divide-border text-sm">
        {house.members.map((m) => (
          <li key={m.user_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span className="font-medium">
              {m.display_name}
              {m.user_id === me && <span className="font-normal text-muted"> (you)</span>}
            </span>
            <span className="text-muted">{m.user_id}</span>
          </li>
        ))}
      </ul>
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Add a flatmate</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="User id" name="user_id" required maxLength={128} placeholder="ayse" autoComplete="off" hint="The id they sign in with." />
          <Field label="Display name" name="display_name" maxLength={100} placeholder="Ayşe" autoComplete="off" />
        </div>
        <Button type="submit" variant="ghost" disabled={saving} className="self-start">
          {saving ? "Adding" : "Add member"}
        </Button>
        <ErrorText error={error} />
      </form>
    </div>
  );
}
