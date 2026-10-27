import type { Metadata } from "next";
import { ExpensesHeader, ExpensesView } from "@/features/expenses/ExpensesView";

export const metadata: Metadata = { title: "Expenses" };

export default function ExpensesPage() {
  return (
    <>
      <ExpensesHeader />
      <ExpensesView />
    </>
  );
}
