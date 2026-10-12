import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { ExpensesView } from "@/features/expenses/ExpensesView";

export const metadata: Metadata = { title: "Expenses" };

export default function ExpensesPage() {
  return (
    <>
      <PageHeader title="Expenses" subtitle="Everything you spent, newest first." />
      <ExpensesView />
    </>
  );
}
