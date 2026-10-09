import type { Expense } from "@/lib/api";
import { Money } from "@/components/ui";

export function ExpenseList({ expenses, empty }: { expenses: Expense[]; empty: string }) {
  if (expenses.length === 0) return <p className="text-sm text-muted">{empty}</p>;
  return (
    <div className="-mx-5 overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-muted">
          <tr className="border-b border-border">
            <th className="px-5 py-2 font-medium">Date</th>
            <th className="px-2 py-2 font-medium">Merchant</th>
            <th className="px-2 py-2 font-medium">Category</th>
            <th className="px-5 py-2 text-right font-medium">Total</th>
          </tr>
        </thead>
        <tbody>
          {expenses.map((e) => (
            <tr key={e.id} className="border-b border-border last:border-0">
              <td className="px-5 py-2 whitespace-nowrap text-muted tabular-nums">{e.expense_date}</td>
              <td className="px-2 py-2">
                {e.merchant}
                {e.source === "receipt" && (
                  <span className="ml-2 rounded bg-accent/15 px-1.5 py-0.5 text-xs text-accent">receipt</span>
                )}
                {e.items.length > 0 && <span className="ml-2 text-xs text-muted">{e.items.length} items</span>}
              </td>
              <td className="px-2 py-2 text-muted">{e.category ?? "—"}</td>
              <td className="px-5 py-2 text-right whitespace-nowrap">
                <Money amount={e.total} currency={e.currency} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
