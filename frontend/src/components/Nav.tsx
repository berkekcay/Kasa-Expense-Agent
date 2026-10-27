"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type FormEvent, useState } from "react";
import { firebaseEnabled, signInWithGoogle, signOut } from "@/lib/auth";
import { useMe } from "@/lib/hooks";
import { switchUser, useAuthUser, useUserId } from "@/lib/user";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/expenses", label: "Expenses" },
  { href: "/receipts", label: "Receipt" },
  { href: "/import", label: "Import" },
  { href: "/inbox", label: "Inbox" },
  { href: "/houses", label: "House" },
  { href: "/budgets", label: "Budgets" },
  { href: "/subscriptions", label: "Subscriptions" },
  { href: "/chat", label: "Ask Kasa" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [openedAt, setOpenedAt] = useState(pathname);
  // Close the phone menu after navigating.
  if (open && openedAt !== pathname) {
    setOpen(false);
    setOpenedAt(pathname);
  }

  const links = (
    <ul className="flex flex-col gap-1 text-sm xl:flex-row xl:gap-0.5">
      {LINKS.map((link) => {
        const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
        return (
          <li key={link.href}>
            <Link
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={`block whitespace-nowrap rounded-md px-3 py-2 xl:px-2 xl:py-1.5 ${active ? "bg-accent/15 font-medium text-accent" : "text-muted hover:text-foreground"}`}
            >
              {link.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );

  return (
    <nav aria-label="Main" className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-6xl flex-wrap 2xl:max-w-7xl items-center gap-x-5 gap-y-2 px-4 py-3 xl:flex-nowrap">
        <Link href="/" className="text-lg font-bold tracking-tight">
          Kasa
        </Link>
        <button
          type="button"
          className="ml-auto inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm xl:hidden"
          aria-expanded={open}
          aria-controls="main-menu"
          onClick={() => {
            setOpen((o) => !o);
            setOpenedAt(pathname);
          }}
        >
          <span aria-hidden className="flex w-4 flex-col gap-[3px]">
            <span className="h-0.5 rounded bg-current" />
            <span className="h-0.5 rounded bg-current" />
            <span className="h-0.5 rounded bg-current" />
          </span>
          Menu
        </button>
        <div
          id="main-menu"
          className={`${open ? "flex" : "hidden"} w-full flex-col gap-3 pb-2 xl:flex xl:w-auto xl:flex-1 xl:flex-row xl:items-center xl:pb-0`}
        >
          {links}
          <div className="flex flex-wrap items-center gap-3 xl:ml-auto xl:flex-nowrap">
            <MyName />
            {firebaseEnabled ? <AccountMenu /> : <DevUserSwitcher compact />}
          </div>
        </div>
      </div>
    </nav>
  );
}

/** The Kasa display name (set in Settings), linked to where it can be changed. */
function MyName() {
  const me = useMe();
  if (!me.data) return null;
  return (
    <Link
      href="/settings"
      className="max-w-40 truncate whitespace-nowrap text-sm font-medium hover:underline xl:max-w-28"
      title="Change your name in Settings"
    >
      {me.data.display_name}
    </Link>
  );
}

export function AccountMenu() {
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
          <span className="text-muted">{user.email ?? user.displayName}</span>
          <button
            type="button"
            onClick={() => run(signOut)}
            className="h-8 rounded-md border border-border px-2 hover:bg-foreground/5"
          >
            Sign out
          </button>
        </>
      ) : (
        <button
          type="button"
          onClick={() => run(signInWithGoogle)}
          className="h-8 rounded-md bg-accent px-3 text-accent-foreground hover:opacity-90"
        >
          Sign in with Google
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
 * `compact` hides the label on wide screens so the nav bar stays on one row. */
export function DevUserSwitcher({ idPrefix = "dev-user", compact = false }: { idPrefix?: string; compact?: boolean }) {
  const userId = useUserId();

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const value = new FormData(e.currentTarget).get("user");
    switchUser(String(value ?? ""));
  }

  return (
    <form key={userId} onSubmit={onSubmit} className="flex items-center gap-2 text-sm">
      <label htmlFor={idPrefix} className={`whitespace-nowrap text-muted ${compact ? "xl:sr-only" : ""}`}>
        Dev user
      </label>
      <input
        id={idPrefix}
        name="user"
        defaultValue={userId}
        autoComplete="off"
        placeholder="Dev user"
        title="Dev user"
        className="h-8 w-28 min-w-0 rounded-md border border-border bg-background px-2 xl:w-24"
      />
      <button type="submit" className="h-8 whitespace-nowrap rounded-md border border-border px-2 hover:bg-foreground/5">
        Switch
      </button>
    </form>
  );
}
