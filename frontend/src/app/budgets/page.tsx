import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { BudgetsView } from "@/features/budgets/BudgetsView";

export const metadata: Metadata = { title: "Budgets" };

export default function Page() {
  return (
    <>
      <PageHeader title="Budgets" subtitle="Monthly limits per category, with alerts before you go over." />
      <BudgetsView />
    </>
  );
}
