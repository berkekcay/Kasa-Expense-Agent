"use client";

import {
  CircleHelp,
  CreditCard,
  FileUp,
  Home,
  Inbox,
  LayoutDashboard,
  type LucideIcon,
  Menu,
  MessageSquareText,
  Monitor,
  Moon,
  PiggyBank,
  Repeat,
  ScanLine,
  Settings,
  Sun,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { useChatBusy } from "@/features/chat/chatStore";
import { api } from "@/lib/api";
import { firebaseEnabled, signInWithGoogle, signOut } from "@/lib/auth";
import { useApi, useDataVersion, useMe } from "@/lib/hooks";
import { LOCALES, defineMessages, setLocale, useLocale, useT } from "@/lib/i18n";
import { type ThemeChoice, setTheme, useThemeChoice } from "@/lib/theme";
import { switchUser, useAuthUser, useUserId } from "@/lib/user";
import { Logo } from "./Logo";

const messages = defineMessages({
  en: {
    overview: "Overview",
    moneyIn: "Money in",
    plan: "Plan",
    shared: "Shared",
    dashboard: "Dashboard",
    chat: "Ask Kasa",
    expenses: "Expenses",
    receipts: "Scan receipt",
    import: "Import statement",
    inbox: "Inbox",
    budgets: "Budgets",
    subscriptions: "Subscriptions",
    house: "House",
    settings: "Settings",
    help: "Help",
    openMenu: "Open menu",
    closeMenu: "Close menu",
    main: "Main",
    answering: "Kasa is answering",
    pending: "pending",
    theme: "Theme",
    light: "Light",
    system: "System",
    dark: "Dark",
    language: "Language",
    changeName: "Change your name in Settings",
    devUser: "Dev user",
    switch: "Switch",
    signOut: "Sign out",
    signIn: "Sign in with Google",
  },
  tr: {
    overview: "Genel",
    moneyIn: "Harcamalar",
    plan: "Plan",
    shared: "Ortak",
    dashboard: "Özet",
    chat: "Kasa'ya sor",
    expenses: "Harcamalar",
    receipts: "Fiş tara",
    import: "Ekstre yükle",
    inbox: "Gelen kutusu",
    budgets: "Bütçeler",
    subscriptions: "Abonelikler",
    house: "Ev",
    settings: "Ayarlar",
    help: "Yardım",
    openMenu: "Menüyü aç",
    closeMenu: "Menüyü kapat",
    main: "Ana menü",
    answering: "Kasa cevaplıyor",
    pending: "bekliyor",
    theme: "Tema",
    light: "Açık",
    system: "Sistem",
    dark: "Koyu",
    language: "Dil",
    changeName: "Adını Ayarlar'dan değiştir",
    devUser: "Dev kullanıcı",
    switch: "Geç",
    signOut: "Çıkış yap",
    signIn: "Google ile giriş yap",
  },
});
type Key = keyof (typeof messages)["en"];

type Item = { href: string; label: Key; icon: LucideIcon };

const GROUPS: { title: Key; items: Item[] }[] = [
  {
    title: "overview",
    items: [
      { href: "/", label: "dashboard", icon: LayoutDashboard },
      { href: "/chat", label: "chat", icon: MessageSquareText },
    ],
  },
  {
    title: "moneyIn",
    items: [
      { href: "/expenses", label: "expenses", icon: CreditCard },
      { href: "/receipts", label: "receipts", icon: ScanLine },
      { href: "/import", label: "import", icon: FileUp },
      { href: "/inbox", label: "inbox", icon: Inbox },
    ],
  },
  {
    title: "plan",
    items: [
      { href: "/budgets", label: "budgets", icon: PiggyBank },
      { href: "/subscriptions", label: "subscriptions", icon: Repeat },
    ],
  },
  {
    title: "shared",
    items: [{ href: "/houses", label: "house", icon: Home }],
  },
];

const isActive = (href: string, pathname: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

/** The app frame: a fixed sidebar on large screens, a top bar with a drawer on small ones. */
export function Nav() {
  const t = useT(messages);
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [openedAt, setOpenedAt] = useState(pathname);
  // Close the drawer after navigating.
  if (open && openedAt !== pathname) {
    setOpen(false);
    setOpenedAt(pathname);
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-sidebar/90 px-4 backdrop-blur lg:hidden">
        <button
          type="button"
          aria-expanded={open}
          aria-controls="main-menu"
          aria-label={t("openMenu")}
          onClick={() => {
            setOpen(true);
            setOpenedAt(pathname);
          }}
          className="-ml-1 inline-flex size-9 items-center justify-center rounded-lg hover:bg-foreground/5"
        >
          <Menu className="size-5" />
        </button>
        <Brand />
      </header>

      {open && (
        <div aria-hidden className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px] lg:hidden" onClick={() => setOpen(false)} />
      )}

      <nav
        id="main-menu"
        aria-label={t("main")}
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-sidebar transition-transform duration-200 lg:translate-x-0 ${open ? "translate-x-0 shadow-pop" : "-translate-x-full"}`}
      >
        <div className="flex h-14 shrink-0 items-center justify-between px-5 lg:h-16">
          <Brand />
          <button
            type="button"
            aria-label={t("closeMenu")}
            onClick={() => setOpen(false)}
            className="inline-flex size-8 items-center justify-center rounded-lg text-muted hover:bg-foreground/5 lg:hidden"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-3 pb-4">
          {GROUPS.map((group) => (
            <div key={group.title} className="mt-4 first:mt-1">
              <p className="px-3 pb-1.5 text-[11px] font-semibold tracking-wider text-muted/80 uppercase">{t(group.title)}</p>
              <ul className="flex flex-col gap-0.5">
                {group.items.map((item) => (
                  <NavLink key={item.href} item={item} active={isActive(item.href, pathname)} />
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="flex shrink-0 flex-col gap-3 border-t border-border p-3">
          <ul>
            <NavLink item={{ href: "/help", label: "help", icon: CircleHelp }} active={isActive("/help", pathname)} />
            <NavLink item={{ href: "/settings", label: "settings", icon: Settings }} active={isActive("/settings", pathname)} />
          </ul>
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <ThemeSwitch />
            <LanguageSwitch />
          </div>
          <UserBox />
        </div>
      </nav>
    </>
  );
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
      <Logo className="size-8" />
      <span className="text-[17px]">Kasa</span>
    </Link>
  );
}

function NavLink({ item, active }: { item: Item; active: boolean }) {
  const t = useT(messages);
  const userId = useUserId();
  const chatBusy = useChatBusy(userId);
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={item.href}
        aria-current={active ? "page" : undefined}
        className={`group flex h-9 items-center gap-3 rounded-lg px-3 text-sm transition ${
          active ? "bg-accent-soft font-medium text-accent" : "text-muted hover:bg-foreground/5 hover:text-foreground"
        }`}
      >
        <Icon aria-hidden className="size-[18px] shrink-0" strokeWidth={active ? 2.2 : 1.8} />
        <span className="flex-1 truncate">{t(item.label)}</span>
        {item.href === "/chat" && chatBusy && (
          <span className="flex items-center gap-1.5 text-xs text-accent">
            <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-accent motion-reduce:animate-none" />
            <span className="sr-only">{t("answering")}</span>
          </span>
        )}
        {item.href === "/inbox" && <InboxCount />}
      </Link>
    </li>
  );
}

function InboxCount() {
  const t = useT(messages);
  const changed = useDataVersion("inbox");
  const expenses = useDataVersion("expenses");
  const pending = useApi(() => api.inbox.list("pending"), [changed, expenses]);
  const n = pending.data?.length ?? 0;
  if (n === 0) return null;
  return (
    <span className="min-w-5 rounded-full bg-accent px-1.5 text-center text-[11px] leading-5 font-semibold text-accent-foreground tabular-nums">
      {n}
      <span className="sr-only"> {t("pending")}</span>
    </span>
  );
}

const THEMES: { value: ThemeChoice; label: Key; icon: LucideIcon }[] = [
  { value: "light", label: "light", icon: Sun },
  { value: "system", label: "system", icon: Monitor },
  { value: "dark", label: "dark", icon: Moon },
];

function ThemeSwitch() {
  const t = useT(messages);
  const choice = useThemeChoice();
  return (
    <div role="radiogroup" aria-label={t("theme")} className="grid grid-cols-3 gap-1 rounded-lg bg-foreground/[0.04] p-1">
      {THEMES.map((theme) => {
        const Icon = theme.icon;
        const on = choice === theme.value;
        return (
          <button
            key={theme.value}
            type="button"
            role="radio"
            aria-checked={on}
            title={t(theme.label)}
            onClick={() => setTheme(theme.value)}
            className={`flex h-7 items-center justify-center rounded-md text-xs transition ${on ? "bg-card font-medium text-foreground shadow-card" : "text-muted hover:text-foreground"}`}
          >
            <Icon aria-hidden className="size-3.5" />
            <span className="sr-only">{t(theme.label)}</span>
          </button>
        );
      })}
    </div>
  );
}

/** TR / EN toggle. */
function LanguageSwitch() {
  const t = useT(messages);
  const locale = useLocale();
  return (
    <div role="radiogroup" aria-label={t("language")} className="flex gap-1 rounded-lg bg-foreground/[0.04] p-1">
      {LOCALES.map((l) => (
        <button
          key={l.value}
          type="button"
          role="radio"
          aria-checked={locale === l.value}
          lang={l.value}
          title={l.label}
          onClick={() => setLocale(l.value)}
          className={`h-7 rounded-md px-2 text-xs font-semibold uppercase transition ${locale === l.value ? "bg-card text-foreground shadow-card" : "text-muted hover:text-foreground"}`}
        >
          {l.value}
        </button>
      ))}
    </div>
  );
}

function UserBox() {
  const t = useT(messages);
  const me = useMe();
  const userId = useUserId();
  const name = me.data?.display_name || userId || "?";
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-2.5">
      <Link href="/settings" className="flex min-w-0 items-center gap-2.5" title={t("changeName")}>
        <span
          aria-hidden
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent uppercase"
        >
          {name.slice(0, 1)}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{name}</span>
          {!firebaseEnabled && <span className="block truncate text-xs text-muted">dev: {userId}</span>}
        </span>
      </Link>
      {firebaseEnabled ? <AccountMenu /> : <DevUserSwitcher compact />}
    </div>
  );
}

export function AccountMenu() {
  const t = useT(messages);
  const user = useAuthUser();
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {user ? (
        <>
          <span className="min-w-0 truncate text-muted">{user.email ?? user.displayName}</span>
          <button
            type="button"
            onClick={() => run(signOut)}
            className="h-8 rounded-md border border-border px-2 hover:bg-foreground/5"
          >
            {t("signOut")}
          </button>
        </>
      ) : (
        <button
          type="button"
          onClick={() => run(signInWithGoogle)}
          className="h-8 rounded-md bg-accent px-3 text-accent-foreground hover:opacity-90"
        >
          {t("signIn")}
        </button>
      )}
      {error && (
        <span role="alert" className="text-danger">
          {error}
        </span>
      )}
    </div>
  );
}

/** Dev mode only (no Firebase config): pick any user id, sent as X-User-Id.
 * `compact` hides the label visually (the sidebar box already says "dev"). */
export function DevUserSwitcher({ idPrefix = "dev-user", compact = false }: { idPrefix?: string; compact?: boolean }) {
  const t = useT(messages);
  const userId = useUserId();

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const value = new FormData(e.currentTarget).get("user");
    switchUser(String(value ?? ""));
  }

  return (
    <form key={userId} onSubmit={onSubmit} className="flex min-w-0 items-center gap-2 text-sm">
      <label htmlFor={idPrefix} className={`whitespace-nowrap text-muted ${compact ? "sr-only" : ""}`}>
        {t("devUser")}
      </label>
      <input
        id={idPrefix}
        name="user"
        defaultValue={userId}
        autoComplete="off"
        placeholder={t("devUser")}
        title={t("devUser")}
        className={`h-8 min-w-0 rounded-md border border-border bg-background px-2 ${compact ? "flex-1" : "w-28"}`}
      />
      <button type="submit" className="h-8 whitespace-nowrap rounded-md border border-border px-2 hover:bg-foreground/5">
        {t("switch")}
      </button>
    </form>
  );
}
