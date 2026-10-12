"use client";

import { useState } from "react";
import { api, type Subscription } from "@/lib/api";
import { capitalize, formatDate } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { useToast } from "@/components/Toast";
import { Async, Badge, Button, Card, Empty, Money, Spinner, errorMessage } from "@/components/ui";

export function SubscriptionsView() {
  const [showDismissed, setShowDismissed] = useState(false);
  const list = useApi(() => api.subscriptions.list(showDismissed), [showDismissed]);
  const upcoming = useApi(() => api.subscriptions.upcoming(30), []);
  const [detecting, setDetecting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const notify = useToast();

  async function detect() {
    setDetecting(true);
    try {
      const found = await api.subscriptions.detect();
      notify(
        found.length === 0 ? "No recurring charges found." : `Found ${found.length} active ${found.length === 1 ? "subscription" : "subscriptions"}.`,
        "success",
      );
      list.reload();
      upcoming.reload();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setDetecting(false);
    }
  }

  async function dismiss(s: Subscription) {
    setBusyId(s.id);
    try {
      await api.subscriptions.dismiss(s.id);
      notify(`${s.display_name} is no longer treated as a subscription.`, "success");
      list.reload();
      upcoming.reload();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={detect} disabled={detecting}>
          {detecting ? (
            <>
              <Spinner /> Scanning
            </>
          ) : (
            "Scan my expenses"
          )}
        </Button>
        <p className="text-sm text-muted">Kasa looks for the same merchant charging a similar amount every week, month or year.</p>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_1.4fr]">
        <Card title="Next 30 days">
          <Async {...upcoming} label="Loading upcoming charges">
            {(rows) =>
              rows.length === 0 ? (
                <Empty>No charges expected in the next 30 days.</Empty>
              ) : (
                <ul className="flex flex-col divide-y divide-border text-sm">
                  {rows.map((s) => (
                    <li key={s.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{s.display_name}</span>
                        <span className="text-muted">{formatDate(s.next_expected_date)}</span>
                      </span>
                      <Money amount={s.amount} currency={s.currency} className="tabular-nums" />
                    </li>
                  ))}
                </ul>
              )
            }
          </Async>
        </Card>

        <Card
          title="Detected subscriptions"
          actions={
            <label className="flex items-center gap-2 text-sm text-muted">
              <input
                type="checkbox"
                checked={showDismissed}
                onChange={(e) => setShowDismissed(e.target.checked)}
                className="size-4 accent-[var(--accent)]"
              />
              Show dismissed
            </label>
          }
        >
          <Async {...list} label="Loading subscriptions">
            {(rows) =>
              rows.length === 0 ? (
                <Empty>Nothing detected yet. Scan your expenses after a few months of data.</Empty>
              ) : (
                <ul className="flex flex-col divide-y divide-border text-sm">
                  {rows.map((s) => (
                    <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                      <div className="min-w-0">
                        <p className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{s.display_name}</span>
                          <Badge>{capitalize(s.period)}</Badge>
                          {s.status === "dismissed" && <Badge tone="warning">Dismissed</Badge>}
                        </p>
                        <p className="mt-0.5 text-muted">
                          Last {formatDate(s.last_charge_date)} · next {formatDate(s.next_expected_date)}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <Money amount={s.amount} currency={s.currency} className="font-medium tabular-nums" />
                        {s.status === "active" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => dismiss(s)}
                            disabled={busyId === s.id}
                            aria-label={`Dismiss ${s.display_name}`}
                          >
                            Not a subscription
                          </Button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )
            }
          </Async>
        </Card>
      </div>
    </div>
  );
}
