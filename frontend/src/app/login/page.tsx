import type { Metadata } from "next";
import { Suspense } from "react";
import { LoginView } from "@/features/auth/LoginView";

export const metadata: Metadata = { title: "Sign in", robots: { index: false, follow: false } };

export default function Page() {
  return (
    // The view reads ?next=..., which is only known in the browser.
    <Suspense>
      <LoginView />
    </Suspense>
  );
}
