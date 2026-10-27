import { render, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { Expense } from "@/lib/api";
import { ExpensesView } from "./ExpensesView";

vi.mock("@/lib/auth", () => ({ authHeader: vi.fn().mockResolvedValue(null) }));
vi.mock("@/lib/user", () => ({ useUserId: () => "test-user" }));

const expense: Expense = {
  id: 1, owner_id: "test-user", house_id: null,
  merchant: "Test Market", expense_date: "2026-10-12", currency: "TRY",
  total: "1234.50", total_minor: 123450, category: "groceries", source: "receipt",
  note: null, items: [], shares: [], split_type: null,
  original_currency: null, original_total: null, original_total_minor: null,
  fx_rate: null, fx_date: null, subscription_id: null, warnings: [],
};
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

it("loads expenses from the API and renders each row's details and actions", async () => {
  fetchMock.mockResolvedValue(new Response(JSON.stringify([
    expense,
    { ...expense, id: 2, merchant: "Test Cafe", total: "45.00", total_minor: 4500, category: "dining", source: "manual" },
  ]), { headers: { "X-Total-Count": "2" } }));

  render(<ExpensesView />);
  expect(await screen.findByText("Test Market")).toBeInTheDocument();
  const rows = screen.getAllByRole("listitem");
  expect(rows).toHaveLength(2);
  const market = within(rows[0]);
  expect(market.getByText("₺1.234,50")).toBeInTheDocument();
  expect(market.getByText("12 Oct 2026 · Groceries")).toBeInTheDocument();
  expect(market.getByText("receipt")).toBeInTheDocument();
  expect(market.getByRole("button", { name: "Edit Test Market" })).toBeInTheDocument();
  expect(market.getByRole("button", { name: "Delete Test Market" })).toBeInTheDocument();
  expect(within(rows[1]).getByText("Test Cafe")).toBeInTheDocument();
  expect(within(rows[1]).getByText("₺45,00")).toBeInTheDocument();
  expect(screen.getByText("2 expenses.")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/expenses\?limit=50$/), expect.any(Object));
});

it("shows the empty state when the API returns no expenses", async () => {
  fetchMock.mockResolvedValue(new Response("[]", { headers: { "X-Total-Count": "0" } }));
  render(<ExpensesView />);
  expect(await screen.findByText("No expenses yet. Add one or scan a receipt.")).toBeInTheDocument();
  expect(screen.queryAllByRole("listitem")).toHaveLength(0);
});
