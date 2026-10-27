"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, Loading } from "@/components/ui";
import type { AuthStep } from "@/lib/api";
import { useHydrated } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { messages } from "./messages";
import { AuthShell, TwoFactorFlow, authLinkClass, safeNext } from "./parts";

type Fragment =
  | { kind: "pending"; pending: string; step: AuthStep; next: string }
  | { kind: "error"; message: string }
  | { kind: "missing" };

/** The API sends Google sign-ins back to /login/continue#pending=..&step=..&next=.. or #error=.. */
export function readFragment(hash: string): Fragment {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const error = params.get("error");
  if (error) return { kind: "error", message: error };
  const pending = params.get("pending");
  const step = params.get("step");
  if (pending && (step === "totp" || step === "totp_setup")) {
    return { kind: "pending", pending, step, next: safeNext(params.get("next")) };
  }
  return { kind: "missing" };
}

/** /login/continue: the Google return. The fragment only exists in the browser, so nothing is
 *  read until after hydration. */
export function LoginContinueView() {
  const hydrated = useHydrated();
  const t = useT(messages);
  if (!hydrated) {
    return (
      <AuthShell title={t("continueTitle")}>
        <Loading />
      </AuthShell>
    );
  }
  return <Continue />;
}

function Continue() {
  const t = useT(messages);
  const router = useRouter();
  // Read once on mount; the effect below then takes the token out of the address bar.
  const [fragment] = useState<Fragment>(() => readFragment(window.location.hash));

  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    }
  }, []);

  if (fragment.kind === "pending") {
    return (
      <TwoFactorFlow
        key={fragment.pending}
        pendingToken={fragment.pending}
        step={fragment.step}
        next={fragment.next}
        onRestart={() => router.push(fragment.next === "/" ? "/login" : `/login?next=${encodeURIComponent(fragment.next)}`)}
      />
    );
  }

  return (
    <AuthShell
      title={t("googleError")}
      footer={
        <Link href="/login" className={authLinkClass}>
          {t("backToLogin")}
        </Link>
      }
    >
      <Alert tone="error">{fragment.kind === "error" ? fragment.message : t("missingFragment")}</Alert>
    </AuthShell>
  );
}
