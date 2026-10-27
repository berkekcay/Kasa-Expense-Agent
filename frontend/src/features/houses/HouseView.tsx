"use client";

import { ArrowLeftRight, Home, Plus, Receipt, Trash2, UserPlus, Wallet, X } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { api, type Balances, type Expense, type House } from "@/lib/api";
import { categoryLabel, common } from "@/lib/commonMessages";
import { formatDate, fromMinor, todayIso } from "@/lib/format";
import { dataChanged, useApi, useDataVersion, useHydrated } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useUserId } from "@/lib/user";
import { useToast } from "@/components/Toast";
import { categoryVar } from "@/components/charts";
import {
  Async,
  Badge,
  Button,
  Card,
  Empty,
  ErrorText,
  Field,
  Money,
  SelectField,
  Skeleton,
  StatCard,
  errorMessage,
} from "@/components/ui";
import { ConversionNote } from "@/features/expenses/ExpenseList";
import { InviteCard, focusInviteCard } from "@/features/invites/InviteCard";
import { inviteMessages } from "@/features/invites/messages";
import { RemindersPanel } from "./Reminders";
import { BalanceBars, PaymentHistory, SettleUpPanel } from "./SettleUp";
import { SplitExpenseForm } from "./SplitExpenseForm";
import { houseMessages } from "./messages";
import { AvatarStack, MemberAvatar, joinNames } from "./parts";
import { usePreferredHouse } from "./selection";

export function HouseView() {
  const t = useT(houseMessages);
  const userId = useUserId();
  const joined = useDataVersion("houses"); // reload after joining a house with an invite link
  const houses = useApi(() => api.listHouses(), [joined]);
  const preferred = usePreferredHouse();
  const [selectedId, setSelectedId] = useState<number | null>(preferred);
  const [seenPreferred, setSeenPreferred] = useState(preferred);
  // A house was just joined: open it.
  if (preferred !== seenPreferred) {
    setSeenPreferred(preferred);
    setSelectedId(preferred);
  }
  const [creating, setCreating] = useState(false);

  function created(h: House) {
    setSelectedId(h.id);
    setCreating(false);
    houses.reload();
  }

  return (
    <Async {...houses} label={t("loadingHouses")} fallback={<HouseSkeleton />}>
      {(list) => {
        const house = list.find((h) => h.id === selectedId) ?? list[0] ?? null;
        if (!house) return <NoHouse onCreated={created} />;
        return (
          <HouseDetail
            key={`${house.id}-${userId}`}
            house={house}
            houses={list}
            me={userId}
            onSelect={setSelectedId}
            onHouseChanged={houses.reload}
            onNewHouse={() => setCreating(true)}
            banner={creating && <CreateHouseCard onCreated={created} onCancel={() => setCreating(false)} />}
          />
        );
      }}
    </Async>
  );
}

function HouseSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-8 w-64" />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-32 rounded-2xl" />
      </div>
      <div className="grid gap-6 xl:grid-cols-5">
        <Skeleton className="h-72 rounded-2xl xl:col-span-3" />
        <Skeleton className="h-72 rounded-2xl xl:col-span-2" />
      </div>
    </div>
  );
}

function NoHouse({ onCreated }: { onCreated: (h: House) => void }) {
  const t = useT(houseMessages);
  return (
    <div className="flex flex-col gap-6">
      <PageTitle title={t("pageTitle")} subtitle={t("pageSubtitle")} />
      <Card>
        <Empty
          icon={<Home />}
          action={
            <div className="mt-2 w-full max-w-sm text-left">
              <CreateHouseForm onCreated={onCreated} />
            </div>
          }
        >
          {t("noHouse")}
        </Empty>
      </Card>
    </div>
  );
}

/** Same type scale as PageHeader, but the subtitle can hold avatars. */
function PageTitle({ title, subtitle, actions }: { title: string; subtitle: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight sm:text-3xl">{title}</h1>
        <div className="mt-1.5 text-sm text-muted">{subtitle}</div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

function HouseDetail({
  house,
  houses,
  me,
  onSelect,
  onHouseChanged,
  onNewHouse,
  banner,
}: {
  house: House;
  houses: House[];
  me: string;
  onSelect: (id: number) => void;
  onHouseChanged: () => void;
  onNewHouse: () => void;
  banner: ReactNode;
}) {
  const t = useT(houseMessages);
  const c = useT(common);
  const [version, setVersion] = useState(0);
  const [adding, setAdding] = useState(false);
  const refresh = () => setVersion((v) => v + 1);
  const balances = useApi(() => api.balances(house.id), [house.id, version]);
  const expenses = useApi(() => api.listHouseExpenses(house.id), [house.id, version]);
  const settlements = useApi(() => api.listSettlements(house.id), [house.id, version]);
  const reminders = useApi(() => api.listReminders(house.id), [house.id, version]);
  const google = useApi(() => api.integrations.googleStatus(), []);
  // Adding someone by user id is a dev tool: real accounts have random ids and join by link.
  const health = useApi(() => api.health(), []);
  const devAuth = health.data?.auth === "dev";
  const name = (id: string) => house.members.find((m) => m.user_id === id)?.display_name ?? id;
  const names = [...house.members]
    .sort((a, b) => Number(b.user_id === me) - Number(a.user_id === me))
    .map((m) => (m.user_id === me ? t("youSubject") : m.display_name));

  // Bring the expense form into view (and focus its first control) when it opens.
  useEffect(() => {
    if (!adding) return;
    const card = document.getElementById("add-expense");
    card?.scrollIntoView({ behavior: "smooth", block: "start" });
    card?.querySelector<HTMLElement>("[role=radio][aria-checked=true]")?.focus({ preventScroll: true });
  }, [adding]);

  return (
    <div className="flex flex-col gap-6">
      <PageTitle
        title={house.name}
        subtitle={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <AvatarStack house={house} />
            <span>
              {joinNames(names)} · {house.currency}
            </span>
          </span>
        }
        actions={
          <>
            {houses.length > 1 && (
              <>
                <label htmlFor="house-select" className="sr-only">
                  {t("houseSelect")}
                </label>
                <select
                  id="house-select"
                  value={house.id}
                  onChange={(e) => onSelect(Number(e.target.value))}
                  className="h-9 max-w-48 rounded-lg border border-border bg-card px-2 text-sm font-medium shadow-card outline-none hover:border-border-strong focus:border-accent focus:ring-2 focus:ring-accent/30"
                >
                  {houses.map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.name}
                    </option>
                  ))}
                </select>
              </>
            )}
            <Button variant="ghost" onClick={onNewHouse}>
              <Home aria-hidden className="size-4" /> {t("newHouse")}
            </Button>
            <Button variant="ghost" onClick={focusInviteCard}>
              <UserPlus aria-hidden className="size-4" /> {t("addFlatmate")}
            </Button>
            <Button onClick={() => setAdding(true)} aria-expanded={adding} aria-controls="add-expense">
              <Plus aria-hidden className="size-4" /> {t("addExpense")}
            </Button>
          </>
        }
      />

      {banner}

      {adding && (
        <Card
          id="add-expense"
          title={t("addCardTitle")}
          description={t("addCardDesc")}
          actions={
            <button
              type="button"
              onClick={() => setAdding(false)}
              aria-label={t("closeForm")}
              className="-mt-1 -mr-1 inline-flex size-8 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 hover:text-foreground"
            >
              <X aria-hidden className="size-4" />
            </button>
          }
          className="scroll-mt-6"
        >
          <SplitExpenseForm house={house} me={me} onSaved={refresh} />
        </Card>
      )}

      <HouseStats house={house} me={me} balances={balances.data} expenses={expenses.data} />

      <div className="grid gap-6 xl:grid-cols-5">
        <Card title={t("balancesTitle")} description={t("balancesDesc")} className="xl:col-span-3">
          <Async {...balances} label={t("loadingBalances")} fallback={<RowsSkeleton rows={house.members.length} />}>
            {(b) => <BalanceBars house={house} balances={b} me={me} name={name} />}
          </Async>
        </Card>
        <Card title={t("settleTitle")} description={t("settleDesc")} className="xl:col-span-2">
          <Async {...balances} label={t("loadingTransfers")} fallback={<RowsSkeleton rows={2} />}>
            {(b) => <SettleUpPanel house={house} balances={b} me={me} name={name} onChanged={refresh} />}
          </Async>
        </Card>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-5">
        <Card
          title={t("expensesTitle")}
          description={t("expensesDesc")}
          className="xl:col-span-3"
          actions={
            !adding && (
              <Button size="sm" variant="subtle" onClick={() => setAdding(true)}>
                <Plus aria-hidden className="size-3.5" /> {c("add")}
              </Button>
            )
          }
        >
          <Async {...expenses} label={t("loadingExpenses")} fallback={<RowsSkeleton rows={4} />}>
            {(rows) => (
              <HouseExpenses
                house={house}
                rows={rows}
                me={me}
                name={name}
                onChanged={refresh}
                onAdd={() => setAdding(true)}
              />
            )}
          </Async>
        </Card>
        <div className="flex min-w-0 flex-col gap-6 xl:col-span-2">
          <Card title={t("paymentsTitle")} description={t("paymentsDesc")}>
            <Async {...settlements} label={t("loadingPayments")} fallback={<RowsSkeleton rows={2} />}>
              {(rows) => <PaymentHistory house={house} settlements={rows} me={me} name={name} onChanged={refresh} />}
            </Async>
          </Card>
          <Card title={t("remindersTitle")} description={t("remindersDesc")}>
            <Async {...reminders} label={t("loadingReminders")} fallback={<RowsSkeleton rows={2} />}>
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
          </Card>
        </div>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-5">
        <Card
          id="members"
          title={t("membersTitle")}
          description={t("membersDesc", { n: house.members.length, house: house.name })}
          className="xl:col-span-3"
        >
          <Members
            house={house}
            me={me}
            devAuth={devAuth}
            onChanged={() => {
              onHouseChanged();
              refresh();
            }}
          />
        </Card>
        <InviteCard house={house} className="xl:col-span-2" />
      </div>
    </div>
  );
}

function RowsSkeleton({ rows }: { rows: number }) {
  return (
    <div aria-hidden className="flex flex-col gap-4">
      {Array.from({ length: Math.max(1, rows) }, (_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="size-8 rounded-lg" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-4 w-20" />
        </div>
      ))}
    </div>
  );
}

function HouseStats({
  house,
  me,
  balances,
  expenses,
}: {
  house: House;
  me: string;
  balances: Balances | null;
  expenses: Expense[] | null;
}) {
  const t = useT(houseMessages);
  const hydrated = useHydrated();
  const month = hydrated ? todayIso().slice(0, 7) : null;
  const loading = <Skeleton className="h-8 w-28" />;

  const mine = balances?.balances.find((b) => b.user_id === me) ?? null;
  // Integer minor units only; summed here and formatted with fromMinor.
  const thisMonth =
    expenses && month ? expenses.filter((e) => e.expense_date.startsWith(month) && e.currency === house.currency) : null;
  const monthTotal = thisMonth?.reduce((s, e) => s + e.total_minor, 0) ?? 0;
  const monthMine = thisMonth?.reduce((s, e) => s + (e.shares.find((x) => x.user_id === me)?.amount_minor ?? 0), 0) ?? 0;
  const transfers = balances?.transfers ?? [];
  const toMove = transfers.reduce((s, t) => s + t.amount_minor, 0);

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <StatCard
        icon={<Wallet />}
        label={t("yourBalance")}
        value={
          !balances ? (
            loading
          ) : !mine || mine.balance_minor === 0 ? (
            <span>{t("settled")}</span>
          ) : (
            <Money
              amount={mine.balance}
              currency={balances.currency}
              signed
              className={mine.balance_minor > 0 ? "text-positive" : "text-danger"}
            />
          )
        }
        footer={
          balances &&
          (!mine || mine.balance_minor === 0
            ? t("nothingOpen")
            : mine.balance_minor > 0
              ? t("owedToYou")
              : t("youOweHouse"))
        }
      />
      <StatCard
        icon={<Receipt />}
        label={t("sharedMonth")}
        value={thisMonth ? <Money amount={fromMinor(monthTotal)} currency={house.currency} /> : loading}
        footer={
          thisMonth && (
            <span>
              {t("monthBills", { n: thisMonth.length })}{" "}
              <Money amount={fromMinor(monthMine)} currency={house.currency} className="font-medium text-foreground" />
            </span>
          )
        }
      />
      <StatCard
        icon={<ArrowLeftRight />}
        label={t("toSettle")}
        value={
          !balances ? loading : transfers.length === 0 ? t("allSettled") : t("transferCount", { n: transfers.length })
        }
        footer={
          balances &&
          (transfers.length === 0 ? (
            t("noOneOwes")
          ) : (
            <span>
              {t("totalBefore")}
              <Money amount={fromMinor(toMove)} currency={balances.currency} className="font-medium text-foreground" />
              {t("totalAfter")}
            </span>
          ))
        }
      />
    </div>
  );
}

const SHOWN = 8;

function HouseExpenses({
  house,
  rows,
  me,
  name,
  onChanged,
  onAdd,
}: {
  house: House;
  rows: Expense[];
  me: string;
  name: (id: string) => string;
  onChanged: () => void;
  onAdd: () => void;
}) {
  const t = useT(houseMessages);
  const notify = useToast();
  const [confirm, setConfirm] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [all, setAll] = useState(false);
  const who = (id: string) => (id === me ? t("youObject") : name(id));

  async function remove(e: Expense) {
    setBusy(e.id);
    try {
      await api.deleteHouseExpense(house.id, e.id);
      notify(t("deletedToast", { merchant: e.merchant }), "success");
      setConfirm(null);
      onChanged();
      dataChanged("expenses");
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  if (rows.length === 0) {
    return (
      <Empty
        icon={<Receipt />}
        action={
          <Button size="sm" variant="ghost" onClick={onAdd}>
            <Plus aria-hidden className="size-3.5" /> {t("addFirst")}
          </Button>
        }
      >
        {t("noExpenses")}
      </Empty>
    );
  }

  const shown = all ? rows : rows.slice(0, SHOWN);
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col divide-y divide-border text-sm">
        {shown.map((e) => {
          const share = e.shares.find((s) => s.user_id === me) ?? null;
          const hasDetail = e.shares.length > 0 || e.items.length > 0 || Boolean(e.note);
          return (
            <li key={e.id} className="py-3 first:pt-0 last:pb-0">
              <div className="flex items-center justify-between gap-3">
                <span className="flex min-w-0 items-center gap-3">
                  <span
                    aria-hidden
                    className="relative flex size-8 shrink-0 items-center justify-center rounded-lg bg-foreground/[0.05] text-xs font-semibold text-foreground/70 uppercase"
                  >
                    {e.merchant.slice(0, 1)}
                    <span
                      className="absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full ring-2 ring-[var(--card)]"
                      style={{ background: categoryVar(e.category ?? "") }}
                    />
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-center gap-2">
                      <span className="truncate font-medium">{e.merchant}</span>
                      {e.split_type && <Badge>{t(`split.${e.split_type}`)}</Badge>}
                    </span>
                    <span className="block text-xs text-muted">
                      {formatDate(e.expense_date)}
                      {e.category && ` · ${categoryLabel(e.category)}`} · {t("paidBy", { who: who(e.owner_id) })}
                    </span>
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  <span className="text-right">
                    {e.shares.length === 0 ? (
                      <Money amount={e.total} currency={e.currency} className="font-medium tabular-nums" />
                    ) : (
                      <>
                        <span className="sr-only">{t("yourShareSr")} </span>
                        {share ? (
                          <Money amount={share.amount} currency={e.currency} className="font-medium tabular-nums" />
                        ) : (
                          <span className="text-xs text-muted">{t("notInSplit")}</span>
                        )}
                        <span className="block text-xs text-muted">
                          {t("ofTotal")} <Money amount={e.total} currency={e.currency} className="tabular-nums" />
                        </span>
                      </>
                    )}
                    <ConversionNote e={e} />
                  </span>
                  {e.owner_id === me && confirm !== e.id && (
                    <button
                      type="button"
                      onClick={() => setConfirm(e.id)}
                      aria-label={t("deleteAria", { merchant: e.merchant })}
                      title={t("deleteExpense")}
                      className="ml-1 inline-flex size-7 items-center justify-center rounded-md text-muted hover:bg-foreground/5 hover:text-danger"
                    >
                      <Trash2 aria-hidden className="size-4" />
                    </button>
                  )}
                </span>
              </div>
              {confirm === e.id && (
                <div className="mt-2 flex flex-wrap items-center gap-2 pl-11">
                  <span className="text-xs text-muted">{t("deleteConfirm")}</span>
                  <Button size="sm" variant="danger" onClick={() => remove(e)} disabled={busy === e.id}>
                    {busy === e.id ? t("deleting") : t("deleteExpense")}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>
                    {t("keep")}
                  </Button>
                </div>
              )}
              {hasDetail && (
                <details className="group mt-1.5 pl-11">
                  <summary className="w-fit cursor-pointer list-none text-xs text-muted hover:text-foreground [&::-webkit-details-marker]:hidden">
                    <span className="group-open:hidden">
                      {e.shares.length > 0
                        ? t("showSplit")
                        : e.items.length > 0
                          ? t("showItems", { n: e.items.length })
                          : t("showNote")}
                    </span>
                    <span className="hidden group-open:inline">{t("hideDetails")}</span>
                  </summary>
                  <ExpenseDetail house={house} e={e} name={who} />
                </details>
              )}
            </li>
          );
        })}
      </ul>
      {rows.length > SHOWN && (
        <Button size="sm" variant="subtle" className="self-start" onClick={() => setAll((v) => !v)}>
          {all ? t("showFewer") : t("showAll", { n: rows.length })}
        </Button>
      )}
    </div>
  );
}

function ExpenseDetail({ house, e, name }: { house: House; e: Expense; name: (id: string) => string }) {
  const t = useT(houseMessages);
  return (
    <div className="mt-2 flex flex-col gap-3 rounded-xl border border-border p-3">
      {e.shares.length > 0 && (
        <ul className="flex flex-col gap-1.5" aria-label={t("sharesAria")}>
          {e.shares.map((s) => (
            <li key={s.user_id} className="flex items-center justify-between gap-3">
              <span className="flex min-w-0 items-center gap-2">
                <MemberAvatar house={house} userId={s.user_id} name={name(s.user_id)} size="sm" />
                <span className="block truncate first-letter:uppercase">{name(s.user_id)}</span>
              </span>
              <Money amount={s.amount} currency={e.currency} className="tabular-nums" />
            </li>
          ))}
        </ul>
      )}
      {e.items.length > 0 && (
        <ul className="flex flex-col gap-1 border-t border-border pt-3 first:border-t-0 first:pt-0" aria-label={t("itemsAria")}>
          {e.items.map((item, i) => (
            <li key={i} className="flex justify-between gap-3">
              <span className="min-w-0">
                {item.description}
                {item.quantity !== "1" && <span className="text-muted"> × {item.quantity}</span>}
                {item.assignees.length > 0 && (
                  <span className="block text-xs text-muted">{item.assignees.map(name).join(", ")}</span>
                )}
              </span>
              <Money amount={item.amount} currency={e.currency} className="tabular-nums" />
            </li>
          ))}
        </ul>
      )}
      {e.note && <p className="text-muted">{e.note}</p>}
    </div>
  );
}

function Members({
  house,
  me,
  devAuth,
  onChanged,
}: {
  house: House;
  me: string;
  devAuth: boolean;
  onChanged: () => void;
}) {
  const t = useT(houseMessages);
  const ti = useT(inviteMessages);
  const notify = useToast();
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const creator = house.created_by === me;
  const last = house.members.length === 1;

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const d = new FormData(form);
    setSaving(true);
    setError(null);
    try {
      const userId = String(d.get("user_id")).trim();
      await api.addMember(house.id, userId, String(d.get("display_name") ?? "").trim());
      notify(t("addedToast", { id: userId }), "success");
      form.reset();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function remove(userId: string, displayName: string) {
    setBusy(userId);
    setRemoveError(null);
    try {
      await api.removeMember(house.id, userId);
      notify(
        userId === me ? t("leftToast", { house: house.name }) : t("removedToast", { name: displayName, house: house.name }),
        "success",
      );
      setConfirm(null);
      onChanged();
      dataChanged("expenses");
    } catch (err) {
      setRemoveError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex min-w-0 flex-col gap-3">
        <ul className="flex flex-col divide-y divide-border text-sm">
          {house.members.map((m) => {
            const you = m.user_id === me;
            const canAct = you ? !last : creator;
            return (
              <li key={m.user_id} className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0 last:pb-0">
                <span className="flex min-w-0 items-center gap-3">
                  <MemberAvatar house={house} userId={m.user_id} name={m.display_name} />
                  <span className="min-w-0">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">
                        {m.display_name}
                        {you && <span className="font-normal text-muted">{t("youTag")}</span>}
                      </span>
                      {m.user_id === house.created_by && <Badge>{t("createdHouse")}</Badge>}
                    </span>
                    <span className="block text-xs text-muted">{m.user_id}</span>
                  </span>
                </span>
                {canAct &&
                  (confirm === m.user_id ? (
                    <span className="flex flex-wrap items-center gap-2">
                      <Button size="sm" variant="danger" onClick={() => remove(m.user_id, m.display_name)} disabled={busy !== null}>
                        {busy === m.user_id ? t("working") : you ? t("leaveHouse") : t("removeName", { name: m.display_name })}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>
                        {you ? t("stay") : t("keep")}
                      </Button>
                    </span>
                  ) : (
                    <Button
                      size="sm"
                      variant="subtle"
                      onClick={() => {
                        setConfirm(m.user_id);
                        setRemoveError(null);
                      }}
                    >
                      {you ? t("leave") : t("remove")}
                    </Button>
                  ))}
              </li>
            );
          })}
        </ul>
        <p className="text-xs text-muted">
          {last ? t("onlyMember") : t("leaveRule")}
          {creator && !last && t("creatorRule")}
        </p>
        <ErrorText error={removeError} />
      </div>
      {devAuth && (
        <form
          onSubmit={onSubmit}
          className="flex max-w-md flex-col gap-3 rounded-xl border border-dashed border-border p-4"
          aria-label={ti("devTitle")}
        >
          <div>
            <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold">
              {ti("devTitle")} <Badge tone="warning">{ti("devBadge")}</Badge>
            </h3>
            <p className="mt-0.5 text-xs text-muted">{ti("devHint")}</p>
          </div>
          <Field
            label={t("userId")}
            name="user_id"
            required
            maxLength={128}
            placeholder="ayse"
            autoComplete="off"
            hint={t("userIdHint")}
          />
          <Field label={t("displayName")} name="display_name" maxLength={100} placeholder="Ayşe" autoComplete="off" />
          <Button type="submit" variant="ghost" disabled={saving} className="self-start">
            <UserPlus aria-hidden className="size-4" />
            {saving ? t("adding") : t("addMember")}
          </Button>
          <ErrorText error={error} />
        </form>
      )}
    </div>
  );
}

function CreateHouseForm({ onCreated, onCancel }: { onCreated: (h: House) => void; onCancel?: () => void }) {
  const t = useT(houseMessages);
  const c = useT(common);
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
    <form onSubmit={onSubmit} className="flex flex-col gap-3" aria-label={t("newHouse")}>
      <div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-3">
        <Field label={t("name")} name="name" required maxLength={100} placeholder={t("namePlaceholder")} />
        <SelectField label={t("currency")} name="currency" defaultValue="TRY">
          {["TRY", "EUR", "USD", "GBP"].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </SelectField>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? t("creating") : t("createHouse")}
        </Button>
        {onCancel && (
          <Button variant="ghost" onClick={onCancel}>
            {c("cancel")}
          </Button>
        )}
      </div>
      <ErrorText error={error} />
    </form>
  );
}

function CreateHouseCard({ onCreated, onCancel }: { onCreated: (h: House) => void; onCancel: () => void }) {
  const t = useT(houseMessages);
  return (
    <Card title={t("newHouse")} description={t("newHouseDesc")}>
      <div className="max-w-md">
        <CreateHouseForm onCreated={onCreated} onCancel={onCancel} />
      </div>
    </Card>
  );
}
