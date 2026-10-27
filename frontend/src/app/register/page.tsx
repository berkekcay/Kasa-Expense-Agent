import type { Metadata } from "next";
import { Suspense } from "react";
import { RegisterView } from "@/features/auth/RegisterView";

export const metadata: Metadata = { title: "Create account", robots: { index: false, follow: false } };

export default function Page() {
  return (
    // The view reads ?next=..., which is only known in the browser.
    <Suspense>
      <RegisterView />
    </Suspense>
  );
}
