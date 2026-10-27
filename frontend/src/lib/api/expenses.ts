// Personal expenses and the fixed category list (shared).
import { del, patch, post, query, request, requestBlob, requestPage } from "./client";

export type ExpenseItem = {
  description: string;
  quantity: string;
  amount: string;
  amount_minor: number;
  assignees: string[];
};
export type ExpenseShare = { user_id: string; amount: string; amount_minor: number };

export type Expense = {
  id: number;
  owner_id: string;
  house_id: number | null;
  merchant: string;
  expense_date: string;
  currency: string; // the base currency once FX lands; the original amount is kept below
  total: string;
  total_minor: number;
  category: string | null;
  source: "manual" | "receipt" | "statement" | "email";
  note: string | null;
  items: ExpenseItem[];
  shares: ExpenseShare[];
  split_type: "equal" | "percent" | "exact" | "items" | null;
  original_currency: string | null;
  original_total: string | null;
  original_total_minor: number | null;
  fx_rate: string | null;
  fx_date: string | null;
  subscription_id: number | null;
  warnings: string[]; // only filled on create responses
};

export type NewExpense = {
  merchant: string;
  total: string;
  expense_date?: string;
  currency?: string;
  category?: string;
  note?: string;
  items?: { description: string; amount: string; quantity?: string }[];
};

/** Server-side filters for GET /expenses. Empty values are left out. */
export type ExpenseFilters = {
  month?: string; // "YYYY-MM"
  category?: string; // a category, or "none" for uncategorised
  source?: Expense["source"] | "";
  scope?: "all" | "personal" | "house";
  limit?: number;
  offset?: number;
};

/** Only these can change; an amount change is delete and add again. */
export type ExpenseChanges = {
  merchant?: string;
  category?: string | null;
  expense_date?: string;
  note?: string | null;
};

const filterQuery = (f: ExpenseFilters) => ({
  month: f.month || undefined,
  category: f.category || undefined,
  source: f.source || undefined,
  scope: f.scope && f.scope !== "all" ? f.scope : undefined,
});

export const expensesApi = {
  listExpenses: (limit = 100) => request<Expense[]>(`/expenses?limit=${limit}`),
  /** One page of the user's expenses plus the total that match the filters. */
  listExpensePage: (f: ExpenseFilters = {}) =>
    requestPage<Expense>(`/expenses${query({ ...filterQuery(f), limit: f.limit, offset: f.offset || undefined })}`),
  /** Every expense that matches the filters as a UTF-8 CSV (no paging). */
  exportExpensesCsv: (f: ExpenseFilters = {}) => requestBlob(`/expenses/export.csv${query(filterQuery(f))}`),
  createExpense: (body: NewExpense) => request<Expense>("/expenses", post(body)),
  updateExpense: (id: number, changes: ExpenseChanges) => request<Expense>(`/expenses/${id}`, patch(changes)),
  deleteExpense: (id: number) => request<void>(`/expenses/${id}`, del),
  categories: () => request<{ categories: string[] }>("/categories"),
};
