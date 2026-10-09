"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type FormEvent } from "react";
import { switchUser, useUserId } from "@/lib/user";

const LINKS = [
  { href: "/", label: "Expenses" },
  { href: "/receipts", label: "Receipt" },
  { href: "/houses", label: "House" },
  { href: "/chat", label: "Ask Kasa" },
];

export function Nav() {
  const pathname = usePathname();
  const userId = useUserId();

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const value = new FormData(e.currentTarget).get("user");
    switchUser(String(value ?? ""));
  }

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
        {/* Dev-only user switcher (sends X-User-Id). Replaced by Firebase sign-in later. */}
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
      </div>
    </nav>
  );
}
