import type { Metadata } from "next";
import { Suspense } from "react";
import { Loading, PageHeader } from "@/components/ui";
import { SettingsView } from "@/features/settings/SettingsView";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
  return (
    <>
      <PageHeader title="Settings" subtitle="Connect Google (Gmail and Calendar) and manage your account." />
      {/* The view reads ?google=... from the OAuth redirect, which is only known at request time. */}
      <Suspense fallback={<Loading />}>
        <SettingsView />
      </Suspense>
    </>
  );
}
