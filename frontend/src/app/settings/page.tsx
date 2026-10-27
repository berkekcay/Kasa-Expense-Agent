import type { Metadata } from "next";
import { Suspense } from "react";
import { Loading } from "@/components/ui";
import { SettingsHeader, SettingsView } from "@/features/settings/SettingsView";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
  return (
    <>
      {/* A client component, so the header follows the chosen language. */}
      <SettingsHeader />
      {/* The view reads ?google=... from the OAuth redirect, which is only known at request time. */}
      <Suspense fallback={<Loading />}>
        <SettingsView />
      </Suspense>
    </>
  );
}
