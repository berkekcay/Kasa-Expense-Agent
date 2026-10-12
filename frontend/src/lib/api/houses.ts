// Houses (owner: track HOUSE): members, split expenses, balances, payments, reminders.
import { del, patch, post, query, request } from "./client";
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
  currency?: string;
  category?: string;
  paid_by?: string;
  split_between?: string[];
};

type SplitBase = {
  merchant: string;
  total: string;
  expense_date?: string;
  currency?: string;
  category?: string;
  note?: string;
  paid_by?: string;
};

export type SplitExpense =
  | (SplitBase & { split_type: "equal"; participants?: string[] })
  | (SplitBase & { split_type: "percent"; percents: Record<string, string> })
  | (SplitBase & { split_type: "exact"; amounts: Record<string, string> })
  | (SplitBase & {
      split_type: "items";
      items: { description: string; amount: string; quantity?: string; assignees: string[] }[];
      participants?: string[];
    });

export type SplitType = SplitExpense["split_type"];

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

export type NewSettlement = {
  from_user: string;
  to_user: string;
  amount: string;
  note?: string;
  allow_overpayment?: boolean;
};

export type ReminderStatus = "scheduled" | "done" | "cancelled";

export type Reminder = {
  id: number;
  house_id: number;
  from_user: string;
  to_user: string;
  amount: string;
  amount_minor: number;
  currency: string;
  due_date: string;
  status: ReminderStatus;
  calendar_event_id: string | null;
  created_by: string;
  created_at: string | null;
};

export type RemindersCreated = { reminders: Reminder[]; calendar_connected: boolean; warnings: string[] };

export const housesApi = {
  listHouses: () => request<House[]>("/houses"),
  createHouse: (name: string, currency = "TRY") => request<House>("/houses", post({ name, currency })),
  addMember: (houseId: number, userId: string, displayName?: string) =>
    request<House>(`/houses/${houseId}/members`, post({ user_id: userId, display_name: displayName || null })),
  listHouseExpenses: (houseId: number) => request<Expense[]>(`/houses/${houseId}/expenses`),
  addHouseExpense: (houseId: number, body: NewHouseExpense) =>
    request<Expense>(`/houses/${houseId}/expenses`, post(body)),
  addSplitExpense: (houseId: number, body: SplitExpense) =>
    request<Expense>(`/houses/${houseId}/expenses/split`, post(body)),
  balances: (houseId: number) => request<Balances>(`/houses/${houseId}/balances`),
  listSettlements: (houseId: number) => request<Settlement[]>(`/houses/${houseId}/settlements`),
  recordSettlement: (houseId: number, body: NewSettlement) =>
    request<Settlement>(`/houses/${houseId}/settlements`, post(body)),
  deleteSettlement: (houseId: number, settlementId: number) =>
    request<void>(`/houses/${houseId}/settlements/${settlementId}`, del),
  createReminders: (houseId: number, dueDate: string, addToCalendar: boolean) =>
    request<RemindersCreated>(`/houses/${houseId}/reminders`, post({ due_date: dueDate, add_to_calendar: addToCalendar })),
  listReminders: (houseId: number, status?: ReminderStatus) =>
    request<Reminder[]>(`/houses/${houseId}/reminders${query({ status })}`),
  setReminderStatus: (houseId: number, reminderId: number, status: ReminderStatus) =>
    request<Reminder>(`/houses/${houseId}/reminders/${reminderId}`, patch({ status })),
};
