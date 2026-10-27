"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { Button, Spinner, errorMessage } from "@/components/ui";
import { ApiError, type Pending, api } from "@/lib/api";
import { useAuthMode } from "@/lib/authMode";
import { useT } from "@/lib/i18n";
import { useSession } from "@/lib/user";
import { messages } from "./messages";
import {
  AuthShell,
  FormError,
  GoogleSection,
  PasswordInput,
  TextInput,
  TwoFactorFlow,
  authLinkClass,
  safeNext,
  useFocusOnMount,
} from "./parts";

/** /login: email and password, then the authenticator code (or first-time setup). */
export function LoginView() {
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const router = useRouter();
  const session = useSession();
  const [pending, setPending] = useState<Pending | null>(null);
  const [email, setEmail] = useState("");

  // Already signed in (another tab, or the back button): go on.
  useEffect(() => {
    if (session && !pending) router.replace(next);
  }, [session, pending, next, router]);

  if (pending) {
    return (
      <TwoFactorFlow
        key={pending.pending_token}
        pendingToken={pending.pending_token}
        step={pending.step}
        next={next}
        onRestart={() => setPending(null)}
      />
    );
  }
  return <LoginForm next={next} email={email} onEmail={setEmail} onPending={setPending} />;
}

function LoginForm({
  next,
  email,
  onEmail,
  onPending,
}: {
  next: string;
  email: string;
  onEmail: (email: string) => void;
  onPending: (pending: Pending) => void;
}) {
  const t = useT(messages);
  const auth = useAuthMode();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ text: string; detail?: string } | null>(null);
  const emailRef = useFocusOnMount<HTMLInputElement>();
  const nextQuery = next === "/" ? "" : `?next=${encodeURIComponent(next)}`;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError({ text: t("errLoginEmpty") });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onPending(await api.auth.login(email.trim(), password));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError({ text: t("wrongPassword") });
      else if (err instanceof ApiError && err.status === 423) setError({ text: t("locked"), detail: err.message });
      else setError({ text: errorMessage(err) });
      setPassword("");
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title={t("loginTitle")}
      subtitle={t("loginSubtitle")}
      footer={
        <>
          {t("noAccount")}{" "}
          <Link href={`/register${nextQuery}`} className={authLinkClass}>
            {t("createAccount")}
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
        <TextInput
          id="login-email"
          label={t("email")}
          type="email"
          name="email"
          autoComplete="username"
          inputMode="email"
          autoCapitalize="none"
          spellCheck={false}
          value={email}
          onChange={(e) => onEmail(e.target.value)}
          error={Boolean(error) && !email.trim()}
          inputRef={emailRef}
          required
        />
        <PasswordInput
          id="login-password"
          label={t("password")}
          name="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={Boolean(error)}
          required
        />
        {error && (
          <FormError>
            <p>{error.text}</p>
            {error.detail && <p className="mt-0.5 text-xs">{error.detail}</p>}
          </FormError>
        )}
        <Button type="submit" disabled={busy} className="h-10 w-full">
          {busy && <Spinner className="size-3.5" />}
          {busy ? t("signingIn") : t("signIn")}
        </Button>
      </form>
      {auth.googleLogin && <GoogleSection next={next} />}
    </AuthShell>
  );
}
