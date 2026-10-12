// Houses (owner: track HOUSE). Add split-type and reminder calls here.
import { post, request } from "./client";
import type { Expense } from "./expenses";

export type House = {
  id: number;
  name: string;
  currency: string;
  members: { user_id: string; display_name: string }[];
};

export type NewHouseExpense = {
  merchant: string;
  total: string;
  expense_date?: string;
  paid_by?: string;
  split_between?: string[];
};

export type Balances = {
  house_id: number;
  currency: string;
  balances: { user_id: string; balance: string; balance_minor: number }[];
  transfers: { from_user: string; to_user: string; amount: string; amount_minor: number }[];
};

export type Settlement = {
  id: number;
  house_id: number;
  from_user: string;
  to_user: string;
  amount: string;
  amount_minor: number;
  currency: string;
  note: string | null;
  created_by: string;
  created_at: string;
};

export type NewSettlement = { from_user: string; to_user: string; amount: string; note?: string };

export const housesApi = {
  listHouses: () => request<House[]>("/houses"),
  createHouse: (name: string, currency = "TRY") => request<House>("/houses", post({ name, currency })),
  addMember: (houseId: number, userId: string, displayName?: string) =>
    request<House>(`/houses/${houseId}/members`, post({ user_id: userId, display_name: displayName || null })),
  listHouseExpenses: (houseId: number) => request<Expense[]>(`/houses/${houseId}/expenses`),
  addHouseExpense: (houseId: number, body: NewHouseExpense) =>
    request<Expense>(`/houses/${houseId}/expenses`, post(body)),
  balances: (houseId: number) => request<Balances>(`/houses/${houseId}/balances`),
  listSettlements: (houseId: number) => request<Settlement[]>(`/houses/${houseId}/settlements`),
  recordSettlement: (houseId: number, body: NewSettlement) =>
    request<Settlement>(`/houses/${houseId}/settlements`, post(body)),
};
