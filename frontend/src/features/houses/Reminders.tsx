"use client";

import { Bell, BellPlus, CalendarCheck, CalendarX2, Check } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useState } from "react";
import { api, type GoogleStatus, type House, type Reminder, type ReminderStatus, type RemindersCreated } from "@/lib/api";
import { formatDate, todayIso } from "@/lib/format";
import { useHydrated } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useToast } from "@/components/Toast";
import { DatePicker } from "@/components/pickers";
import { Alert, Badge, Button, Empty, ErrorText, Money, errorMessage } from "@/components/ui";
import { houseMessages } from "./messages";
import { DateChip } from "./parts";

const STATUS_TONE = { scheduled: "accent", done: "positive", cancelled: "neutral" } as const;

export function RemindersPanel({
  house,
  reminders,
  google,
  hasTransfers,
  me,
  name,
  onChanged,
}: {
  house: House;
  reminders: Reminder[];
  google: GoogleStatus | null;
  hasTransfers: boolean;
  me: string;
  name: (id: string) => string;
  onChanged: () => void;
}) {
  const t = useT(houseMessages);
  const notify = useToast();
  const hydrated = useHydrated();
  const calendarReady = Boolean(google?.connected && google.calendar_access);
  const [addToCalendarChoice, setAddToCalendar] = useState<boolean | null>(null);
  const addToCalendar = addToCalendarChoice ?? calendarReady;
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<RemindersCreated | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [confirmCancel, setConfirmCancel] = useState<number | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const due = String(new FormData(e.currentTarget).get("due_date") ?? "");
    if (!due) {
      setError(t("errDueDate"));
      return;
    }
    setSaving(true);
    setError(null);
    setCreated(null);
    try {
      const res = await api.createReminders(house.id, due, addToCalendar);
      setCreated(res);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function setStatus(r: Reminder, status: ReminderStatus) {
    setBusyId(r.id);
    try {
      await api.setReminderStatus(house.id, r.id, status);
      notify(
        status === "done" ? t("markedPaid") : status === "cancelled" ? t("reminderCancelled") : t("markedNotPaid"),
        "success",
      );
      setConfirmCancel(null);
      onChanged();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {google !== null &&
        (calendarReady ? (
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <CalendarCheck aria-hidden className="size-4 text-positive" />
            <span>{t("calConnected")}</span>
            {google.google_email && <span className="text-muted">{google.google_email}</span>}
          </p>
        ) : (
          <p className="flex items-start gap-2 text-sm text-muted">
            <CalendarX2 aria-hidden className="mt-0.5 size-4 shrink-0" />
            <span>
              {t("calNotConnected")}{" "}
              <Link href="/settings" className="font-medium text-accent hover:underline">
                {t("connectIt")}
              </Link>
            </span>
          </p>
        ))}

      <form onSubmit={onSubmit} className="flex flex-col gap-3 rounded-xl border border-border p-4">
        <div>
          <h3 className="text-sm font-semibold">{t("remindTitle")}</h3>
          <p className="mt-0.5 text-xs text-muted">
            {t("remindHint")}
            {calendarReady && t("remindCalHint")}
          </p>
        </div>
        <DatePicker
          label={t("dueDate")}
          name="due_date"
          required
          min={hydrated ? todayIso() : undefined}
          placeholder={t("pickDueDate")}
        />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={addToCalendar}
            onChange={(e) => setAddToCalendar(e.target.checked)}
            className="size-4 accent-[var(--accent)]"
          />
          {t("addToCalendar")}
        </label>
        <Button type="submit" disabled={saving || !hasTransfers} className="self-start">
          <BellPlus aria-hidden className="size-4" />
          {saving ? t("creating") : t("createReminders")}
        </Button>
        {!hasTransfers && <p className="text-xs text-muted">{t("nothingToRemind")}</p>}
        <ErrorText error={error} />
        <div aria-live="polite" className="flex flex-col gap-2 empty:hidden">
          {created && (
            <Alert tone="success" onDismiss={() => setCreated(null)}>
              {t("remindersCreated", { n: created.reminders.length })}
              {created.calendar_connected && t("onCalendar")}
              {created.cancelled.length > 0 && t("remindersReplaced", { n: created.cancelled.length })}
            </Alert>
          )}
          {created?.warnings.map((w) => (
            <Alert key={w} tone="warning">
              {w}
            </Alert>
          ))}
        </div>
      </form>

      {reminders.length === 0 ? (
        <Empty icon={<Bell />}>{t("noReminders")}</Empty>
      ) : (
        <ul className="flex flex-col divide-y divide-border text-sm" aria-label={t("remindersTitle")}>
          {reminders.map((r) => (
            <li key={r.id} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
              <div className="flex items-start gap-3">
                <DateChip
                  iso={r.due_date}
                  tone={r.status === "scheduled" ? (r.outdated ? "neutral" : "accent") : r.status === "done" ? "neutral" : "muted"}
                />
                <div className="min-w-0 flex-1">
                  <p className={`flex items-baseline justify-between gap-3 ${r.status === "cancelled" ? "text-muted" : ""}`}>
                    <span className="min-w-0 font-medium">
                      {t("willPay", {
                        from: r.from_user === me ? t("youSubject") : name(r.from_user),
                        to: r.to_user === me ? t("youObject") : name(r.to_user),
                        fromMe: r.from_user === me ? 1 : 0,
                        toMe: r.to_user === me ? 1 : 0,
                      })}
                    </span>
                    <Money amount={r.amount} currency={r.currency} className="shrink-0 font-semibold tabular-nums" />
                  </p>
                  <p className="mt-0.5 text-xs text-muted">
                    {t("due", { date: formatDate(r.due_date) })}
                    {r.cancel_reason === "outdated" && t("replacedNote")}
                    {r.outdated && t("outdatedNote")}
                  </p>
                  <p className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    {r.cancel_reason === "outdated" ? (
                      <Badge>{t("updated")}</Badge>
                    ) : (
                      <Badge tone={STATUS_TONE[r.status]}>{t(`status.${r.status}`)}</Badge>
                    )}
                    {r.outdated && <Badge tone="warning">{t("outOfDate")}</Badge>}
                    {r.calendar_event_id && r.status !== "cancelled" && <Badge>{t("inCalendar")}</Badge>}
                  </p>
                </div>
              </div>
              {r.status !== "cancelled" && (
                <div className="flex flex-wrap items-center gap-2 pl-[3.25rem]">
                  {r.status === "scheduled" && (
                    <Button size="sm" variant="ghost" onClick={() => setStatus(r, "done")} disabled={busyId === r.id}>
                      <Check aria-hidden className="size-3.5" />
                      {t("markPaid")}
                    </Button>
                  )}
                  {r.status === "done" && (
                    <Button size="sm" variant="subtle" onClick={() => setStatus(r, "scheduled")} disabled={busyId === r.id}>
                      {t("notPaidYet")}
                    </Button>
                  )}
                  {r.created_by === me &&
                    (confirmCancel === r.id ? (
                      <>
                        <Button size="sm" variant="danger" onClick={() => setStatus(r, "cancelled")} disabled={busyId === r.id}>
                          {t("cancelReminder")}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setConfirmCancel(null)}>
                          {t("keep")}
                        </Button>
                      </>
                    ) : (
                      <Button size="sm" variant="subtle" onClick={() => setConfirmCancel(r.id)}>
                        {t("cancelShort")}
                      </Button>
                    ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
