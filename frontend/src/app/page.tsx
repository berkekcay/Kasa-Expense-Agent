import { PageHeader } from "@/components/ui";
import { DashboardView } from "@/features/dashboard/DashboardView";

export default function HomePage() {
  return (
    <>
      <PageHeader title="Dashboard" subtitle="This month at a glance." />
      <DashboardView />
    </>
  );
}
