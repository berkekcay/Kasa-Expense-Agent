import { PageHeader } from "@/components/ui";
import { ExpensesView } from "@/features/expenses/ExpensesView";

export default function HomePage() {
  return (
    <>
      <PageHeader title="Expenses" subtitle="Everything you spent, newest first." />
      <ExpensesView />
    </>
  );
}
