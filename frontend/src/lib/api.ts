// Typed client for the Kasa FastAPI backend.
// Money arrives as decimal strings ("123.45") plus exact *_minor integers; never use floats for sums.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const USER_KEY = "kasa.userId";
export const DEFAULT_USER_ID = "dev-user";

// Sprint-1 dev auth: the backend trusts X-User-Id. Firebase ID tokens replace this later.
export function getUserId(): string {
  if (typeof window === "undefined") return DEFAULT_USER_ID;
  try {
    return window.localStorage.getItem(USER_KEY) || DEFAULT_USER_ID;
  } catch {
    return DEFAULT_USER_ID;
  }
}

export function setUserId(userId: string): void {
  try {
    window.localStorage.setItem(USER_KEY, userId);
  } catch {
    // storage unavailable (private mode); the default user is used instead
  }
}

export type ExpenseItem = { description: string; quantity: string; amount: string; amount_minor: number };
export type ExpenseShare = { user_id: string; amount: string; amount_minor: number };

export type Expense = {
  id: number;
  owner_id: string;
  house_id: number | null;
  merchant: string;
  expense_date: string;
  currency: string;
  total: string;
  total_minor: number;
  category: string | null;
  source: "manual" | "receipt" | string;
  note: string | null;
  items: ExpenseItem[];
  shares: ExpenseShare[];
};

export type NewExpense = {
  merchant: string;
  total: string;
  expense_date?: string;
  currency?: string;
  category?: string;
  note?: string;
};

export type ReceiptResult = { expense: Expense; agent_message: string; warnings: string[] };

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

export type ChartSpec = {
  type: "bar" | "line" | "pie";
  title: string;
  x: string;
  y: string;
  data: Record<string, string | number | null>[];
};

export type ChatReply = { session_id: string; text: string; chart: ChartSpec | null };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-User-Id", getUserId());
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request<{ status: string; agents_enabled: boolean }>("/health"),

  listExpenses: () => request<Expense[]>("/expenses"),
  createExpense: (body: NewExpense) => request<Expense>("/expenses", json(body)),

  uploadReceipt: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ReceiptResult>("/receipts", { method: "POST", body: form });
  },

  listHouses: () => request<House[]>("/houses"),
  createHouse: (name: string, currency = "TRY") => request<House>("/houses", json({ name, currency })),
  addMember: (houseId: number, userId: string, displayName?: string) =>
    request<House>(`/houses/${houseId}/members`, json({ user_id: userId, display_name: displayName || null })),
  listHouseExpenses: (houseId: number) => request<Expense[]>(`/houses/${houseId}/expenses`),
  addHouseExpense: (houseId: number, body: NewHouseExpense) =>
    request<Expense>(`/houses/${houseId}/expenses`, json(body)),
  balances: (houseId: number) => request<Balances>(`/houses/${houseId}/balances`),

  chat: (message: string, sessionId?: string | null) =>
    request<ChatReply>("/chat", json({ message, session_id: sessionId ?? null })),
};
