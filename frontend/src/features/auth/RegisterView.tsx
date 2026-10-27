"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";
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
  fill,
  safeNext,
} from "./parts";

export const MIN_PASSWORD = 10;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Level = "short" | "weak" | "fair" | "strong";

/** A rough hint, not a rule: the server only requires 10 characters. */
export function passwordStrength(password: string): Level {
  if (password.length < MIN_PASSWORD) return "short";
  const kinds = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((re) => re.test(password)).length;
  const points = kinds + (password.length >= 14 ? 1 : 0) + (password.length >= 18 ? 1 : 0);
  return points <= 1 ? "weak" : points <= 3 ? "fair" : "strong";
}

const FILLED: Record<Level, number> = { short: 0, weak: 1, fair: 2, strong: 3 };
const COLOR: Record<Level, string> = {
  short: "bg-danger",
  weak: "bg-danger",
  fair: "bg-[var(--status-warning)]",
  strong: "bg-positive",
};

/** Three bars and a short sentence under a new password. */
export function StrengthHint({ password }: { password: string }) {
  const t = useT(messages);
  const level = passwordStrength(password);
  return (
    <span className="flex flex-col gap-1.5 pt-0.5">
      <span aria-hidden className="grid grid-cols-3 gap-1">
        {[0, 1, 2].map((i) => (
          <span key={i} className={`h-1 rounded-full ${i < FILLED[level] ? COLOR[level] : "bg-foreground/10"}`} />
        ))}
      </span>
      <span>
        <span className="sr-only">{t("strengthLabel")}: </span>
        {t(`strength.${level}`, { n: MIN_PASSWORD - password.length })}
      </span>
    </span>
  );
}

type FieldName = "name" | "email" | "password" | "confirm" | "accept";

/** /register: name, email, password and consent, then the mandatory authenticator setup and
 *  the recovery codes. */
export function RegisterView() {
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const router = useRouter();
  const session = useSession();
  const [pending, setPending] = useState<Pending | null>(null);

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
        numbered
        // The account exists now, so starting again means signing in.
        onRestart={() => router.push(`/login${next === "/" ? "" : `?next=${encodeURIComponent(next)}`}`)}
      />
    );
  }
  return <RegisterForm next={next} onPending={setPending} />;
}

function RegisterForm({ next, onPending }: { next: string; onPending: (pending: Pending) => void }) {
  const t = useT(messages);
  const auth = useAuthMode();
  const [values, setValues] = useState({ name: "", email: "", password: "", confirm: "" });
  const [accept, setAccept] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ field: FieldName | null; text: string; taken?: boolean } | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLInputElement>(null);
  const acceptRef = useRef<HTMLInputElement>(null);
  const nextQuery = next === "/" ? "" : `?next=${encodeURIComponent(next)}`;

  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  const set = (field: keyof typeof values) => (e: ChangeEvent<HTMLInputElement>) =>
    setValues((v) => ({ ...v, [field]: e.target.value }));

  function fail(field: FieldName | null, text: string, taken = false) {
    setError({ field, text, taken });
    const ref = { name: nameRef, email: emailRef, password: passwordRef, confirm: confirmRef, accept: acceptRef };
    if (field) ref[field].current?.focus();
  }

  function check(): [FieldName, string] | null {
    if (!values.name.trim()) return ["name", t("errName")];
    if (!EMAIL.test(values.email.trim())) return ["email", t("errEmail")];
    if (values.password.length < MIN_PASSWORD) return ["password", t("errPasswordShort")];
    if (values.password !== values.confirm) return ["confirm", t("errMismatch")];
    if (!accept) return ["accept", t("errAccept")];
    return null;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const problem = check();
    if (problem) return fail(...problem);
    setBusy(true);
    setError(null);
    try {
      onPending(
        await api.auth.register({
          email: values.email.trim(),
          password: values.password,
          display_name: values.name.trim(),
          accept_terms: true,
        }),
      );
    } catch (err) {
      setBusy(false);
      if (err instanceof ApiError && err.status === 409) return fail("email", t("emailTaken"), true);
      if (err instanceof ApiError && (err.status === 400 || err.status === 422)) {
        const field = /mail/i.test(err.message) ? "email" : /password/i.test(err.message) ? "password" : null;
        return fail(field, err.message);
      }
      fail(null, errorMessage(err));
    }
  }

  const invalid = (field: FieldName) => error?.field === field;

  return (
    <AuthShell
      title={t("registerTitle")}
      subtitle={t("registerSubtitle")}
      step={t("stepOf", { n: 1 })}
      footer={
        <>
          {t("haveAccount")}{" "}
          <Link href={`/login${nextQuery}`} className={authLinkClass}>
            {t("signInInstead")}
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4">
        <TextInput
          id="register-name"
          label={t("name")}
          hint={t("nameHint")}
          name="name"
          autoComplete="name"
          maxLength={100}
          value={values.name}
          onChange={set("name")}
          error={invalid("name")}
          inputRef={nameRef}
          required
        />
        <TextInput
          id="register-email"
          label={t("email")}
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          autoCapitalize="none"
          spellCheck={false}
          value={values.email}
          onChange={set("email")}
          error={invalid("email")}
          inputRef={emailRef}
          required
        />
        <PasswordInput
          id="register-password"
          label={t("password")}
          name="new-password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD}
          value={values.password}
          onChange={set("password")}
          error={invalid("password")}
          inputRef={passwordRef}
          hint={<StrengthHint password={values.password} />}
          required
        />
        <PasswordInput
          id="register-confirm"
          label={t("confirmPassword")}
          name="confirm-password"
          autoComplete="new-password"
          value={values.confirm}
          onChange={set("confirm")}
          error={invalid("confirm")}
          inputRef={confirmRef}
          required
        />
        <label className="flex items-start gap-2.5 text-sm">
          <input
            ref={acceptRef}
            type="checkbox"
            name="accept_terms"
            checked={accept}
            onChange={(e) => setAccept(e.target.checked)}
            aria-invalid={invalid("accept") || undefined}
            required
            aria-labelledby="accept-terms-text"
            className="mt-0.5 size-4 shrink-0 accent-[var(--accent)]"
          />
          <span id="accept-terms-text">
            {fill(t("accept"), {
              privacy: (
                <Link href="/privacy" target="_blank" className={authLinkClass}>
                  {t("privacyLink")}
                </Link>
              ),
              terms: (
                <Link href="/terms" target="_blank" className={authLinkClass}>
                  {t("termsLink")}
                </Link>
              ),
            })}
          </span>
        </label>
        {error && (
          <FormError>
            {error.text}{" "}
            {error.taken && (
              <Link href={`/login${nextQuery}`} className="font-medium underline underline-offset-2">
                {t("signInInstead")}
              </Link>
            )}
          </FormError>
        )}
        <Button type="submit" disabled={busy} className="h-10 w-full">
          {busy && <Spinner className="size-3.5" />}
          {busy ? t("registering") : t("register")}
        </Button>
      </form>
      {auth.googleLogin && <GoogleSection next={next} />}
    </AuthShell>
  );
}
