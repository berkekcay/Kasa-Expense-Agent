// Budgets (owner: track MONEY).
import { del, put, query, request } from "./client";

export type Budget = {
  id: number;
  category: string | null; // null = overall
  limit: string;
  limit_minor: number;
  currency: string;
  alert_threshold_pct: number;
};

export type BudgetStatus = {
  budget: Budget;
  month: string;
  spent: string;
  spent_minor: number;
  remaining: string;
  remaining_minor: number;
  pct_used: number;
  level: "ok" | "warning" | "exceeded";
};

export type NewBudget = { category?: string | null; limit: string; currency?: string; alert_threshold_pct?: number };

export const budgetsApi = {
  list: () => request<Budget[]>("/budgets"),
  set: (body: NewBudget) => request<Budget>("/budgets", put(body)),
  remove: (budgetId: number) => request<void>(`/budgets/${budgetId}`, del),
  status: (month?: string) => request<BudgetStatus[]>(`/budgets/status${query({ month })}`),
};
