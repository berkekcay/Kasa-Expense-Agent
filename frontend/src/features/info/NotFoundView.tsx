"use client";

import { ArrowLeft, LifeBuoy } from "lucide-react";
import Link from "next/link";
import { Logo } from "@/components/Logo";
import { defineMessages, useT } from "@/lib/i18n";

const messages = defineMessages({
  en: {
    code: "Error 404",
    title: "We couldn't find that page",
    text: "The link may be old, or the address may have a typo. Your data is safe; nothing has changed.",
    home: "Go to the dashboard",
    help: "Open the help pages",
  },
  tr: {
    code: "Hata 404",
    title: "Bu sayfayı bulamadık",
    text: "Link eski olabilir ya da adreste bir yazım hatası olabilir. Verilerin güvende, hiçbir şey değişmedi.",
    home: "Özete dön",
    help: "Yardım sayfalarını aç",
  },
});

export function NotFoundView() {
  const t = useT(messages);
  return (
    <div className="mx-auto flex max-w-md flex-col items-center py-16 text-center sm:py-24">
      <Logo className="size-14" />
      <p className="mt-6 text-sm font-medium text-accent">{t("code")}</p>
      <h1 className="mt-1 text-[26px] leading-tight font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
      <p className="mt-3 text-sm text-muted">{t("text")}</p>
      <div className="mt-8 flex flex-wrap justify-center gap-2">
        <Link
          href="/"
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-accent-foreground shadow-card hover:brightness-110"
        >
          <ArrowLeft aria-hidden className="size-4" /> {t("home")}
        </Link>
        <Link
          href="/help"
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-4 text-sm font-medium shadow-card hover:bg-card-hover"
        >
          <LifeBuoy aria-hidden className="size-4" /> {t("help")}
        </Link>
      </div>
    </div>
  );
}
