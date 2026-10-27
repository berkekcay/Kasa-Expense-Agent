"use client";

import { FileBarChart, MessageSquareText } from "lucide-react";
import Link from "next/link";
import { Async, Empty, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useDataVersion } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { ReportCard } from "./ReportCard";
import { reportMessages } from "./messages";

const askLink =
  "inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3 text-sm font-medium text-accent-foreground shadow-card hover:brightness-110";

export function ReportsView() {
  const t = useT(reportMessages);
  const version = useDataVersion("reports");
  const list = useApi(() => api.reports.list(), [version]);
  return (
    <>
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle")}
        actions={
          <Link href="/chat" className={askLink}>
            <MessageSquareText aria-hidden className="size-4" /> {t("askKasa")}
          </Link>
        }
      />
      <Async
        {...list}
        label={t("loading")}
        fallback={
          <div className="grid gap-6 lg:grid-cols-2">
            <Skeleton className="h-80 rounded-2xl" />
            <Skeleton className="h-80 rounded-2xl" />
          </div>
        }
      >
        {(reports) =>
          reports.length === 0 ? (
            <Empty icon={<FileBarChart />}>{t("empty")}</Empty>
          ) : (
            <div className="grid gap-6 lg:grid-cols-2">
              {reports.map((r) => (
                <ReportCard key={`${r.id}-${r.title}-${r.pinned}`} report={r} />
              ))}
            </div>
          )
        }
      </Async>
    </>
  );
}

/** The pinned reports on the dashboard; nothing when none are pinned. */
export function PinnedReports() {
  const t = useT(reportMessages);
  const version = useDataVersion("reports");
  const list = useApi(() => api.reports.list(true), [version]);
  const reports = list.data ?? [];
  if (reports.length === 0) return null;
  return (
    <section aria-label={t("pinnedSection")} className="flex flex-col gap-3">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight">{t("pinnedSection")}</h2>
          <p className="text-sm text-muted">{t("pinnedHint")}</p>
        </div>
        <Link href="/reports" className="text-sm font-medium text-accent hover:underline">
          {t("allReports")}
        </Link>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        {reports.map((r) => (
          <ReportCard key={`${r.id}-${r.title}-${r.pinned}`} report={r} compact />
        ))}
      </div>
    </section>
  );
}
