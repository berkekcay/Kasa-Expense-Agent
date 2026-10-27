"use client";

import { ChevronRight, Receipt } from "lucide-react";
import type { ReactNode } from "react";
import type { Expense } from "@/lib/api";
import { categoryLabel, common, sourceLabel } from "@/lib/commonMessages";
import { formatDate, formatMoney, formatMonth } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { Badge, Empty, Money } from "@/components/ui";
import { CategoryIcon } from "./CategoryIcon";
import { messages } from "./messages";

/** Original amount and rate for an expense converted from another currency. */
export function ConversionNote({ e }: { e: Expense }) {
  const t = useT(messages);
  if (!e.original_currency || !e.original_total) return null;
  return (
    <span className="block text-xs text-muted">
      {formatMoney(e.original_total, e.original_currency)}
      {e.fx_rate && ` ${t("atRate", { rate: e.fx_rate })}`}
      {e.fx_date && ` (${formatDate(e.fx_date)})`}
    </span>
  );
}

/** Consecutive rows of the same month, in the order the API sent them (newest first). */
function byMonth(expenses: Expense[]): { month: string; rows: Expense[] }[] {
  const groups: { month: string; rows: Expense[] }[] = [];
  for (const e of expenses) {
    const month = e.expense_date.slice(0, 7);
    const last = groups[groups.length - 1];
    if (last && last.month === month) last.rows.push(e);
    else groups.push({ month, rows: [e] });
  }
  return groups;
}

/**
 * Transaction rows: category icon, merchant with badges, date and category, amount on the right.
 * `memberName` turns user ids into display names for house expenses.
 * `trailing` puts small controls (icon buttons) at the end of a row; `actions` adds a strip
 * under a row (a confirmation); `extra` shows something below it (an edit form).
 * `groupByMonth` adds a month heading when the rows span more than one month.
 */
export function ExpenseList({
  expenses,
  empty,
  emptyAction,
  memberName,
  showSource = true,
  showHouse = false,
  groupByMonth = false,
  trailing,
  actions,
  extra,
}: {
  expenses: Expense[];
  empty: string;
  emptyAction?: ReactNode;
  memberName?: (userId: string) => string;
  showSource?: boolean;
  showHouse?: boolean;
  groupByMonth?: boolean;
  trailing?: (e: Expense) => ReactNode;
  actions?: (e: Expense) => ReactNode;
  extra?: (e: Expense) => ReactNode;
}) {
  const t = useT(messages);
  const tc = useT(common);
  if (expenses.length === 0) {
    return (
      <Empty icon={<Receipt />} action={emptyAction}>
        {empty}
      </Empty>
    );
  }
  const name = memberName ?? ((id: string) => id);
  const groups = groupByMonth ? byMonth(expenses) : [{ month: "", rows: expenses }];
  const headed = groups.length > 1;

  const row = (e: Expense) => {
    const hasDetail = e.shares.length > 0 || e.items.length > 0 || Boolean(e.note);
    const below = actions?.(e);
    const end = trailing?.(e);
    const added = extra?.(e);
    return (
      <li key={e.id} className="py-3 first:pt-0 last:pb-0">
        <div className="flex items-center gap-3">
          <CategoryIcon category={e.category} />
          <div className="min-w-0 flex-1">
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="truncate font-medium">{e.merchant}</span>
              {showHouse && e.house_id !== null && <Badge tone="accent">{tc("house")}</Badge>}
              {e.subscription_id !== null && <Badge>{t("subscription")}</Badge>}
              {showSource && e.source !== "manual" && <Badge>{sourceLabel(e.source)}</Badge>}
              {e.split_type && <Badge>{t(`split.${e.split_type}`)}</Badge>}
            </p>
            <p className="mt-0.5 text-xs text-muted">
              {formatDate(e.expense_date)}
              {e.category && ` · ${categoryLabel(e.category)}`}
              {e.house_id !== null && ` · ${t("paidBy", { name: name(e.owner_id) })}`}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <Money amount={e.total} currency={e.currency} className="font-semibold tabular-nums" />
            <ConversionNote e={e} />
          </div>
          {end && <div className="-mr-1.5 flex shrink-0 items-center">{end}</div>}
        </div>
        {(below || added || hasDetail) && (
          <div className="pl-12">
            {below && <div className="mt-2 flex flex-wrap items-center gap-2">{below}</div>}
            {added}
            {hasDetail && (
              <details className="group mt-1.5">
                <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-md text-xs text-muted hover:text-foreground [&::-webkit-details-marker]:hidden">
                  <ChevronRight aria-hidden className="size-3.5 transition group-open:rotate-90" />
                  {e.shares.length > 0
                    ? t("splitDetails")
                    : e.items.length > 0
                      ? t("itemCount", { n: e.items.length })
                      : t("noteSummary")}
                </summary>
                <div className="mt-2 flex flex-col gap-3 rounded-xl bg-foreground/[0.03] p-3">
                  {e.shares.length > 0 && (
                    <div>
                      <p className="mb-1 text-xs font-medium text-muted">{t("shares")}</p>
                      <ul className="flex flex-col gap-0.5">
                        {e.shares.map((s) => (
                          <li key={s.user_id} className="flex justify-between gap-3">
                            <span>{name(s.user_id)}</span>
                            <Money amount={s.amount} currency={e.currency} className="tabular-nums" />
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {e.items.length > 0 && (
                    <div>
                      <p className="mb-1 text-xs font-medium text-muted">{t("items")}</p>
                      <ul className="flex flex-col gap-0.5">
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
                    </div>
                  )}
                  {e.note && <p className="text-muted">{e.note}</p>}
                </div>
              </details>
            )}
          </div>
        )}
      </li>
    );
  };

  return (
    <div className="flex flex-col gap-6 text-sm">
      {groups.map((g) => (
        <div key={g.month || "all"}>
          {headed && (
            <h3 className="mb-2 flex items-baseline justify-between gap-3 border-b border-border pb-2 text-sm font-semibold">
              {formatMonth(g.month)}
              <span className="text-xs font-normal text-muted">
                {t("groupCount", { n: g.rows.length })}
              </span>
            </h3>
          )}
          <ul className="flex flex-col divide-y divide-border">{g.rows.map(row)}</ul>
        </div>
      ))}
    </div>
  );
}
