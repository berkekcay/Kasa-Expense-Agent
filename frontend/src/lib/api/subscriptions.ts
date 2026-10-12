// Detected subscriptions (owner: track MONEY).
import { query, request } from "./client";

export type Subscription = {
  id: number;
  merchant_key: string;
  display_name: string;
  amount: string;
  amount_minor: number;
  currency: string;
  period: "weekly" | "monthly" | "yearly";
  last_charge_date: string;
  next_expected_date: string;
  status: "active" | "dismissed";
};

export const subscriptionsApi = {
  list: (includeDismissed = false) =>
    request<Subscription[]>(`/subscriptions${query({ include_dismissed: includeDismissed })}`),
  detect: () => request<Subscription[]>("/subscriptions/detect", { method: "POST" }),
  upcoming: (withinDays = 30) => request<Subscription[]>(`/subscriptions/upcoming${query({ within_days: withinDays })}`),
  dismiss: (id: number) => request<Subscription>(`/subscriptions/${id}/dismiss`, { method: "POST" }),
};
