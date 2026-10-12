"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";
import { api, type GoogleStatus, type House, type Reminder, type ReminderStatus, type RemindersCreated } from "@/lib/api";
import { formatDate, todayIso } from "@/lib/format";
import { useHydrated } from "@/lib/hooks";
import { useToast } from "@/components/Toast";
import { Alert, Badge, Button, Empty, ErrorText, Field, Money, errorMessage } from "@/components/ui";

const STATUS_TONE = { scheduled: "accent", done: "positive", cancelled: "neutral" } as const;
const STATUS_LABEL = { scheduled: "Scheduled", done: "Paid", cancelled: "Cancelled" } as const;

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
      setError("Pick a due date.");
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
        status === "done" ? "Marked as paid." : status === "cancelled" ? "Reminder cancelled." : "Marked as not paid yet.",
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
    <div className="flex flex-col gap-6">
      <div className="text-sm">
        {google === null ? null : calendarReady ? (
          <p className="flex flex-wrap items-center gap-2">
            <Badge tone="positive">Google Calendar connected</Badge>
            <span className="text-muted">{google.google_email}</span>
          </p>
        ) : (
          <Alert tone="info">
            Google Calendar is not connected, so reminders stay in Kasa.{" "}
            <Link href="/settings" className="font-medium text-accent underline">
              Connect it in Settings
            </Link>
            .
          </Alert>
        )}
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Remind everyone to settle up</h3>
        <p className="text-sm text-muted">
          Kasa makes one reminder per suggested transfer.
          {calendarReady && " With the calendar on, each one becomes an all day event and both flatmates are invited."}
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Due date" name="due_date" type="date" required min={hydrated ? todayIso() : undefined} className="w-48" />
          <label className="flex h-9 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={addToCalendar}
              onChange={(e) => setAddToCalendar(e.target.checked)}
              className="size-4 accent-[var(--accent)]"
            />
            Add to Google Calendar
          </label>
          <Button type="submit" disabled={saving || !hasTransfers}>
            {saving ? "Creating" : "Create reminders"}
          </Button>
        </div>
        {!hasTransfers && <p className="text-sm text-muted">Everyone is settled up, so there is nothing to remind about.</p>}
        <ErrorText error={error} />
        <div aria-live="polite" className="flex flex-col gap-2">
          {created && (
            <Alert tone="success" onDismiss={() => setCreated(null)}>
              {created.reminders.length === 0
                ? "No reminders were needed."
                : `${created.reminders.length} ${created.reminders.length === 1 ? "reminder is" : "reminders are"} set.`}
              {created.calendar_connected && " They are on your Google Calendar."}
            </Alert>
          )}
          {created?.warnings.map((w) => (
            <Alert key={w} tone="warning">
              {w}
            </Alert>
          ))}
        </div>
      </form>

      <div>
        <h3 className="mb-2 text-sm font-medium">Reminders</h3>
        {reminders.length === 0 ? (
          <Empty>No reminders yet.</Empty>
        ) : (
          <ul className="flex flex-col divide-y divide-border text-sm">
            {reminders.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2">
                    <span>
                      <strong className="font-medium">{r.from_user === me ? "You" : name(r.from_user)}</strong>{" "}
                      {r.from_user === me ? "pay" : "pays"}{" "}
                      <strong className="font-medium">{r.to_user === me ? "you" : name(r.to_user)}</strong>{" "}
                      <Money amount={r.amount} currency={r.currency} className="font-semibold" />
                    </span>
                    <Badge tone={STATUS_TONE[r.status]}>{STATUS_LABEL[r.status]}</Badge>
                    {r.calendar_event_id && <Badge>In calendar</Badge>}
                  </p>
                  <p className="text-muted">Due {formatDate(r.due_date)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {r.status === "scheduled" && (
                    <Button size="sm" variant="ghost" onClick={() => setStatus(r, "done")} disabled={busyId === r.id}>
                      Mark paid
                    </Button>
                  )}
                  {r.status === "done" && (
                    <Button size="sm" variant="subtle" onClick={() => setStatus(r, "scheduled")} disabled={busyId === r.id}>
                      Not paid yet
                    </Button>
                  )}
                  {r.status !== "cancelled" &&
                    r.created_by === me &&
                    (confirmCancel === r.id ? (
                      <>
                        <Button size="sm" variant="danger" onClick={() => setStatus(r, "cancelled")} disabled={busyId === r.id}>
                          Cancel reminder
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setConfirmCancel(null)}>
                          Keep
                        </Button>
                      </>
                    ) : (
                      <Button size="sm" variant="subtle" onClick={() => setConfirmCancel(r.id)}>
                        Cancel
                      </Button>
                    ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
