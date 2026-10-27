"use client";

// Small site footer with the info and legal links. Rendered by the root layout below <main>.

import Link from "next/link";
import { REPO_URL } from "@/features/info/site";
import { defineMessages, useT } from "@/lib/i18n";

const messages = defineMessages({
  en: {
    label: "Site links",
    about: "About",
    help: "Help",
    privacy: "Privacy",
    terms: "Terms",
    cookies: "Cookies",
    github: "GitHub",
    copyright: "© 2026 Kasa · Istinye University student project",
  },
  tr: {
    label: "Site bağlantıları",
    about: "Hakkında",
    help: "Yardım",
    privacy: "Gizlilik",
    terms: "Koşullar",
    cookies: "Çerezler",
    github: "GitHub",
    copyright: "© 2026 Kasa · İstinye Üniversitesi öğrenci projesi",
  },
});

const LINKS = [
  { href: "/about", label: "about" },
  { href: "/help", label: "help" },
  { href: "/privacy", label: "privacy" },
  { href: "/terms", label: "terms" },
  { href: "/cookies", label: "cookies" },
] as const;

const linkClass = "rounded-sm hover:text-foreground hover:underline underline-offset-2";

export function Footer({ className = "" }: { className?: string }) {
  const t = useT(messages);
  return (
    <footer className={`border-t border-border py-6 text-xs text-muted ${className}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <nav aria-label={t("label")}>
          <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
            {LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className={linkClass}>
                  {t(l.label)}
                </Link>
              </li>
            ))}
            <li>
              <a href={REPO_URL} className={linkClass}>
                {t("github")}
              </a>
            </li>
          </ul>
        </nav>
        <p>{t("copyright")}</p>
      </div>
    </footer>
  );
}
