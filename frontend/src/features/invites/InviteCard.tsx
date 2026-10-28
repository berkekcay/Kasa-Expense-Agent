"use client";

// "Invite flatmates" card on the house page: make a link, copy it or send it on WhatsApp,
// and see or cancel the links that still work.

import { Check, Copy, Link2, MessageCircle, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type House, type HouseInvite } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useToast } from "@/components/Toast";
import { Async, Badge, Button, Card, Empty, ErrorText, Skeleton, controlClass, errorMessage } from "@/components/ui";
import { inviteMessages } from "./messages";

export const INVITE_CARD_ID = "invite-flatmates";
const CREATE_BUTTON_ID = "invite-create";

/** Scroll the invite card into view and focus its main button (header "Add flatmate"). */
export function focusInviteCard() {
  const card = document.getElementById(INVITE_CARD_ID);
  card?.scrollIntoView({ behavior: "smooth", block: "start" });
  document.getElementById(CREATE_BUTTON_ID)?.focus({ preventScroll: true });
}

export function InviteCard({ house, className = "" }: { house: House; className?: string }) {
  const t = useT(inviteMessages);
  const notify = useToast();
  const [version, setVersion] = useState(0);
  const invites = useApi(() => api.listInvites(house.id), [house.id, version]);
  const [created, setCreated] = useState<HouseInvite | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The link in the field: the one just made (while the list reloads, or while it is still in
  // it), else the newest link that still works.
  const active = invites.data;
  const current =
    created && (invites.loading || !active || active.some((i) => i.id === created.id))
      ? created
      : (active?.[0] ?? null);

  async function create() {
    setCreating(true);
    setError(null);
    try {
      const invite = await api.createInvite(house.id);
      setCreated(invite);
      setVersion((v) => v + 1);
      notify(t("createdToast"), "success");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setCreating(false);
    }
  }

  return (
    <Card
      id={INVITE_CARD_ID}
      title={t("cardTitle")}
      description={t("cardDesc")}
      className={`scroll-mt-6 ${className}`}
      actions={
        current && (
          <Button id={CREATE_BUTTON_ID} size="sm" variant="subtle" onClick={create} disabled={creating}>
            <Link2 aria-hidden className="size-3.5" /> {creating ? t("creating") : t("newLink")}
          </Button>
        )
      }
    >
      <div className="flex flex-col gap-5">
        {current ? (
          <InviteLink key={current.id} house={house} invite={current} focusOnCreate={created?.id === current.id} />
        ) : (
          <Button id={CREATE_BUTTON_ID} onClick={create} disabled={creating} className="self-start">
            <Link2 aria-hidden className="size-4" /> {creating ? t("creating") : t("createLink")}
          </Button>
        )}
        <ErrorText error={error} />

        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">{t("activeTitle")}</h3>
          <Async
            {...invites}
            label={t("loadingInvites")}
            fallback={<Skeleton className="h-10 w-full rounded-lg" />}
          >
            {(rows) =>
              rows.length === 0 ? (
                <Empty icon={<Link2 />}>{t("noActive")}</Empty>
              ) : (
                <ActiveInvites
                  house={house}
                  rows={rows}
                  onRevoked={(id) => {
                    if (created?.id === id) setCreated(null);
                    setVersion((v) => v + 1);
                  }}
                />
              )
            }
          </Async>
        </div>
      </div>
    </Card>
  );
}

function InviteLink({ house, invite, focusOnCreate }: { house: House; invite: HouseInvite; focusOnCreate: boolean }) {
  const t = useT(inviteMessages);
  const notify = useToast();
  const [copied, setCopied] = useState(false);
  const fieldRef = useRef<HTMLInputElement>(null);
  const fieldId = `invite-link-${invite.id}`;
  const termsId = `${fieldId}-terms`;
  const whatsapp = `https://wa.me/?text=${encodeURIComponent(t("shareText", { house: house.name, url: invite.url }))}`;

  useEffect(() => {
    if (focusOnCreate) fieldRef.current?.focus();
  }, [focusOnCreate]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(invite.url);
      setCopied(true);
      notify(t("copiedToast"), "success");
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      fieldRef.current?.focus();
      fieldRef.current?.select();
      notify(t("copyFailed"), "warning");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={fieldId} className="text-sm text-muted">
        {t("linkLabel")}
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          ref={fieldRef}
          id={fieldId}
          aria-describedby={termsId}
          readOnly
          value={invite.url}
          onFocus={(e) => e.currentTarget.select()}
          className={`${controlClass} font-mono text-[13px]`}
        />
        <Button variant="ghost" onClick={copy} className="shrink-0">
          {copied ? <Check aria-hidden className="size-4" /> : <Copy aria-hidden className="size-4" />}
          {copied ? t("copied") : t("copy")}
        </Button>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p id={termsId} className="text-xs text-muted">
          {t("linkTerms", { date: formatDateTime(invite.expires_at), n: invite.max_uses })}
        </p>
        <a
          href={whatsapp}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-xs font-medium shadow-card hover:border-border-strong hover:bg-card-hover"
        >
          <MessageCircle aria-hidden className="size-3.5" /> {t("whatsapp")}
        </a>
      </div>
    </div>
  );
}

function ActiveInvites({
  house,
  rows,
  onRevoked,
}: {
  house: House;
  rows: HouseInvite[];
  onRevoked: (id: number) => void;
}) {
  const t = useT(inviteMessages);
  const notify = useToast();
  const [confirm, setConfirm] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const name = (id: string) => house.members.find((m) => m.user_id === id)?.display_name ?? id;

  async function revoke(id: number) {
    setBusy(id);
    setError(null);
    try {
      await api.revokeInvite(house.id, id);
      notify(t("revokedToast"), "success");
      setConfirm(null);
      onRevoked(id);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col divide-y divide-border text-sm">
        {rows.map((invite) => (
          <li key={invite.id} className="py-2.5 first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="min-w-0">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[13px] font-medium">{invite.code}</span>
                  <Badge tone={invite.uses > 0 ? "accent" : "neutral"}>
                    {t("uses", { n: invite.uses, max: invite.max_uses })}
                  </Badge>
                </span>
                <span className="block text-xs text-muted">
                  {t("expires", { date: formatDateTime(invite.expires_at) })} · {name(invite.created_by)}
                </span>
              </span>
              {confirm !== invite.id && (
                <button
                  type="button"
                  onClick={() => setConfirm(invite.id)}
                  aria-label={t("revokeAria", { code: invite.code })}
                  title={t("revoke")}
                  className="inline-flex size-7 items-center justify-center rounded-md text-muted hover:bg-foreground/5 hover:text-danger"
                >
                  <Trash2 aria-hidden className="size-4" />
                </button>
              )}
            </div>
            {confirm === invite.id && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-xs text-muted">{t("revokeConfirm")}</span>
                <Button size="sm" variant="danger" onClick={() => revoke(invite.id)} disabled={busy === invite.id}>
                  {busy === invite.id ? t("revoking") : t("revokeYes")}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>
                  {t("keep")}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <ErrorText error={error} />
    </div>
  );
}
