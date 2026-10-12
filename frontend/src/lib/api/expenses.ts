// Personal expenses and the fixed category list (shared).
import { post, request } from "./client";

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

export const expensesApi = {
  listExpenses: (limit = 100) => request<Expense[]>(`/expenses?limit=${limit}`),
  createExpense: (body: NewExpense) => request<Expense>("/expenses", post(body)),
  categories: () => request<{ categories: string[] }>("/categories"),
};
