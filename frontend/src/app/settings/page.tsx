import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { SettingsView } from "@/features/settings/SettingsView";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
  return (
    <>
      <PageHeader title="Settings" subtitle="Connect Google (Gmail and Calendar) and manage your account." />
      <SettingsView />
    </>
  );
}
