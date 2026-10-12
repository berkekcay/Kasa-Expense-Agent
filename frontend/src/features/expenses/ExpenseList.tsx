import type { ReactNode } from "react";
import type { Expense } from "@/lib/api";
import { capitalize, formatDate, formatMoney } from "@/lib/format";
import { Badge, Money } from "@/components/ui";

const SOURCE_LABEL: Record<Expense["source"], string> = {
  manual: "manual",
  receipt: "receipt",
  statement: "statement",
  email: "email",
};

const SPLIT_LABEL: Record<NonNullable<Expense["split_type"]>, string> = {
  equal: "Equal split",
  percent: "Percent split",
  exact: "Exact amounts",
  items: "Per item",
};

/** Original amount and rate for an expense converted from another currency. */
export function ConversionNote({ e }: { e: Expense }) {
  if (!e.original_currency || !e.original_total) return null;
  return (
    <span className="block text-xs text-muted">
      {formatMoney(e.original_total, e.original_currency)}
      {e.fx_rate && ` at ${e.fx_rate}`}
      {e.fx_date && ` (${formatDate(e.fx_date)})`}
    </span>
  );
}

/**
 * Expense rows that stack on phones and stay one line on wider screens.
 * `memberName` turns user ids into display names for house expenses.
 * `actions` adds buttons under a row; `extra` shows something below it (an edit form).
 */
export function ExpenseList({
  expenses,
  empty,
  memberName,
  showSource = true,
  actions,
  extra,
}: {
  expenses: Expense[];
  empty: string;
  memberName?: (userId: string) => string;
  showSource?: boolean;
  actions?: (e: Expense) => ReactNode;
  extra?: (e: Expense) => ReactNode;
}) {
  if (expenses.length === 0) return <p className="text-sm text-muted">{empty}</p>;
  const name = memberName ?? ((id: string) => id);
  return (
    <ul className="flex flex-col divide-y divide-border text-sm">
      {expenses.map((e) => {
        const hasDetail = e.shares.length > 0 || e.items.length > 0 || Boolean(e.note);
        return (
          <li key={e.id} className="py-3 first:pt-0 last:pb-0">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="font-medium">{e.merchant}</span>
                  {showSource && e.source !== "manual" && <Badge tone="accent">{SOURCE_LABEL[e.source]}</Badge>}
                  {e.split_type && <Badge>{SPLIT_LABEL[e.split_type]}</Badge>}
                  {e.subscription_id !== null && <Badge>subscription</Badge>}
                </p>
                <p className="mt-0.5 text-muted">
                  {formatDate(e.expense_date)}
                  {e.category && ` · ${capitalize(e.category)}`}
                  {e.house_id !== null && ` · paid by ${name(e.owner_id)}`}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <Money amount={e.total} currency={e.currency} className="font-medium tabular-nums" />
                <ConversionNote e={e} />
              </div>
            </div>
            {actions && <div className="mt-1.5 flex flex-wrap items-center gap-2">{actions(e)}</div>}
            {extra?.(e)}
            {hasDetail && (
              <details className="mt-1.5">
                <summary className="cursor-pointer text-xs text-muted hover:text-foreground">
                  {e.shares.length > 0 ? "Split details" : e.items.length > 0 ? `${e.items.length} items` : "Note"}
                </summary>
                <div className="mt-2 flex flex-col gap-3 rounded-lg border border-border p-3">
                  {e.shares.length > 0 && (
                    <div>
                      <p className="mb-1 text-xs font-medium text-muted">Shares</p>
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
                      <p className="mb-1 text-xs font-medium text-muted">Items</p>
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
          </li>
        );
      })}
    </ul>
  );
}
