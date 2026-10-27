import type { Metadata } from "next";
import { BudgetsView } from "@/features/budgets/BudgetsView";

export const metadata: Metadata = { title: "Budgets" };

// The view draws its own page header, because the header actions need client state.
export default function Page() {
  return <BudgetsView />;
}
