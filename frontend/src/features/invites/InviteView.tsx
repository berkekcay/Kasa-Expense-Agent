"use client";

// /invite/<code>: where an invite link leads, and a button to join. Signed-out visitors go to
// the login page and come back here afterwards (?next=).

import { Home, LogIn } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, api, type InvitePreview } from "@/lib/api";
import { common } from "@/lib/commonMessages";
import { formatDateTime } from "@/lib/format";
import { dataChanged } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useUserId } from "@/lib/user";
import { useToast } from "@/components/Toast";
import { Alert, Button, Card, ErrorText, Loading, cardLinkClass, errorMessage } from "@/components/ui";
import { preferHouse } from "@/features/houses/selection";
import { inviteMessages } from "./messages";

type State =
  | { status: "loading" }
  | { status: "ready"; preview: InvitePreview }
  | { status: "missing" }
  | { status: "signin" }
  | { status: "error"; message: string };

export function loginPath(code: string): string {
  return `/login?next=${encodeURIComponent(`/invite/${code}`)}`;
}

export function InviteView({ code }: { code: string }) {
  const t = useT(inviteMessages);
  const c = useT(common);
  const router = useRouter();
  const notify = useToast();
  const userId = useUserId();
  const [state, setState] = useState<State>({ status: "loading" });
  const [nonce, setNonce] = useState(0);
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.previewInvite(code).then(
      (preview) => {
        if (!cancelled) setState({ status: "ready", preview });
      },
      (e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) {
          setState({ status: "signin" });
          router.replace(loginPath(code));
        } else if (e instanceof ApiError && e.status === 404) {
          setState({ status: "missing" });
        } else {
          setState({ status: "error", message: errorMessage(e) });
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [code, userId, nonce, router]);

  async function join(preview: InvitePreview) {
    setJoining(true);
    setJoinError(null);
    try {
      const house = await api.acceptInvite(code);
      preferHouse(house.id);
      dataChanged("houses");
      notify(t("joinedToast", { house: preview.house_name }), "success");
      router.push("/houses");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        router.replace(loginPath(code));
        return;
      }
      setJoinError(errorMessage(e));
      setJoining(false);
      setNonce((n) => n + 1); // the link may have just expired or been used up: show why
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-6 py-4 sm:py-10">
      <h1 className="text-[26px] leading-tight font-semibold tracking-tight sm:text-3xl">{t("pageTitle")}</h1>
      <Card>
        {state.status === "loading" && <Loading label={t("checking")} />}
        {state.status === "signin" && (
          <p role="status" className="flex items-center gap-2 text-sm text-muted">
            <LogIn aria-hidden className="size-4" /> {t("signingIn")}
          </p>
        )}
        {state.status === "missing" && (
          <div className="flex flex-col gap-4">
            <Alert tone="warning" title={t("notFoundTitle")}>
              {t("notFound")}
            </Alert>
            <Link href="/" className={`${cardLinkClass} self-start`}>
              {t("goHome")}
            </Link>
          </div>
        )}
        {state.status === "error" && (
          <div className="flex flex-col items-start gap-2">
            <ErrorText error={state.message} />
            <Button variant="ghost" size="sm" onClick={() => setNonce((n) => n + 1)}>
              {c("tryAgain")}
            </Button>
          </div>
        )}
        {state.status === "ready" && (
          <Preview preview={state.preview} joining={joining} joinError={joinError} onJoin={join} />
        )}
      </Card>
    </div>
  );
}

function Preview({
  preview,
  joining,
  joinError,
  onJoin,
}: {
  preview: InvitePreview;
  joining: boolean;
  joinError: string | null;
  onJoin: (p: InvitePreview) => void;
}) {
  const t = useT(inviteMessages);
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-4">
        <span
          aria-hidden
          className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent [&>svg]:size-6"
        >
          <Home />
        </span>
        <div className="min-w-0">
          <h2 className="truncate text-xl font-semibold tracking-tight">{preview.house_name}</h2>
          <p className="text-sm text-muted">{t("invitedBy", { who: preview.invited_by })}</p>
        </div>
      </div>

      {preview.already_member ? (
        <>
          <Alert tone="success">{t("alreadyMember")}</Alert>
          <Link
            href="/houses"
            className="inline-flex h-9 items-center justify-center gap-1.5 self-start rounded-lg bg-accent px-4 text-sm font-medium text-accent-foreground shadow-card hover:brightness-110"
          >
            <Home aria-hidden className="size-4" /> {t("openHouse")}
          </Link>
        </>
      ) : preview.usable ? (
        <>
          <p className="text-sm text-muted">{t("validUntil", { date: formatDateTime(preview.expires_at) })}</p>
          <Button onClick={() => onJoin(preview)} disabled={joining} className="self-start">
            <Home aria-hidden className="size-4" /> {joining ? t("joining") : t("join")}
          </Button>
          <ErrorText error={joinError} />
        </>
      ) : (
        <>
          <Alert tone="warning" title={t("cantJoin")}>
            {preview.reason ? t(`reason.${preview.reason}`) : preview.message}
          </Alert>
          <Link href="/" className={`${cardLinkClass} self-start`}>
            {t("goHome")}
          </Link>
        </>
      )}
    </div>
  );
}
