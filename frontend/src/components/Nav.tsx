"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type FormEvent, useState } from "react";
import { firebaseEnabled, signInWithGoogle, signOut } from "@/lib/auth";
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

  return (
    <nav className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold tracking-tight">
          Kasa
        </Link>
        <ul className="flex flex-wrap gap-1 text-sm">
          {LINKS.map((link) => {
            const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className={`rounded-md px-3 py-1.5 ${active ? "bg-accent/15 font-medium text-accent" : "text-muted hover:text-foreground"}`}
                >
                  {link.label}
                </Link>
              </li>
            );
          })}
        </ul>
        {firebaseEnabled ? <AccountMenu /> : <DevUserSwitcher />}
      </div>
    </nav>
  );
}

function AccountMenu() {
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
    <div className="ml-auto flex items-center gap-2 text-sm">
      {user ? (
        <>
          <span className="text-muted">{user.displayName ?? user.email}</span>
          <button onClick={() => run(signOut)} className="h-8 rounded-md border border-border px-2 hover:bg-foreground/5">
            Sign out
          </button>
        </>
      ) : (
        <button
          onClick={() => run(signInWithGoogle)}
          className="h-8 rounded-md bg-accent px-3 text-accent-foreground hover:opacity-90"
        >
          Sign in with Google
        </button>
      )}
      {error && <span className="text-danger">{error}</span>}
    </div>
  );
}

/** Dev mode only (no Firebase config): pick any user id, sent as X-User-Id. */
function DevUserSwitcher() {
  const userId = useUserId();

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const value = new FormData(e.currentTarget).get("user");
    switchUser(String(value ?? ""));
  }

  return (
    <form key={userId} onSubmit={onSubmit} className="ml-auto flex items-center gap-2 text-sm">
      <label htmlFor="dev-user" className="text-muted">
        Dev user
      </label>
      <input
        id="dev-user"
        name="user"
        defaultValue={userId}
        className="h-8 w-32 rounded-md border border-border bg-background px-2"
      />
      <button type="submit" className="h-8 rounded-md border border-border px-2 hover:bg-foreground/5">
        Switch
      </button>
    </form>
  );
}
