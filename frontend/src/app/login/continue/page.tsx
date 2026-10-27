import type { Metadata } from "next";
import { LoginContinueView } from "@/features/auth/LoginContinueView";

export const metadata: Metadata = { title: "Signing in", robots: { index: false, follow: false } };

/** Google sign-in comes back here with #pending=...&step=... (or #error=...). */
export default function Page() {
  return <LoginContinueView />;
}
