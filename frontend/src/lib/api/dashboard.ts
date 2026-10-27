// Home dashboard (owner: track MONEY).
import type { BudgetStatus } from "./budgets";
import { query, request } from "./client";
import type { Subscription } from "./subscriptions";

export type HouseBalance = {
  house_id: number;
  house_name: string;
  balance: string; // positive: the house owes me; negative: I owe
  balance_minor: number;
  currency: string;
};

export type RecentExpense = {
  id: number;
  merchant: string;
  expense_date: string;
  category: string | null;
  house_id: number | null;
  currency: string;
  total: string;
  total_minor: number;
  my_amount: string; // the total for personal expenses, my share for house expenses
  my_amount_minor: number;
};

export type Dashboard = {
  month: string;
  currency: string;
  total: string;
  total_minor: number;
  previous_month_total: string;
  previous_month_total_minor: number;
  by_category: { category: string; total: string; total_minor: number }[];
  budgets: BudgetStatus[];
  upcoming_subscriptions: Subscription[];
  house_balances: HouseBalance[];
  pending_inbox: number;
  trend: { month: string; total: string; total_minor: number }[];
  recent_expenses: RecentExpense[];
  daily: DayTotal[]; // every day of `month`, zeros included
  previous_daily: DayTotal[]; // every day of the month before
  top_merchants: { merchant: string; total: string; total_minor: number; count: number }[];
  previous_by_category: { category: string; total: string; total_minor: number }[];
};

export type DayTotal = { day: string; total: string; total_minor: number };

export const dashboardApi = {
  get: (month?: string) => request<Dashboard>(`/dashboard${query({ month })}`),
};
