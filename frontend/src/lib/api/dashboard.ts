// Home dashboard (owner: track MONEY).
import type { BudgetStatus } from "./budgets";
import { query, request } from "./client";
import type { Subscription } from "./subscriptions";

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
  house_balances: { house_id: number; house_name: string; balance: string; balance_minor: number }[];
  pending_inbox: number;
};

export const dashboardApi = {
  get: (month?: string) => request<Dashboard>(`/dashboard${query({ month })}`),
};
