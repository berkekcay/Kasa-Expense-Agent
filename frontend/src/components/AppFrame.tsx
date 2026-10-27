"use client";

// Picks the page frame by path, and guards the app in accounts mode.
// - Auth pages (/login, /login/continue, /register): no sidebar, the page draws its own card.
// - Info pages (/about, /help, /privacy, /terms, /cookies): no sidebar, a slim top bar.
// - Everything else is the app: sidebar plus content. When the server runs in accounts mode
//   and no session is stored, the page is not rendered and the browser goes to
//   /login?next=<this page>. In dev and firebase mode nothing is forced.

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";
import { useAuthMode } from "@/lib/authMode";
import { useT } from "@/lib/i18n";
import { useSession } from "@/lib/user";
import { Footer } from "./Footer";
import { Logo } from "./Logo";
import { LanguageSwitch, Nav } from "./Nav";
import { Loading } from "./ui";
import { frameMessages } from "./messages";

const AUTH_PAGES = ["/login", "/register"];
const INFO_PAGES = ["/about", "/help", "/privacy", "/terms", "/cookies"];

const under = (pathname: string, roots: string[]) => roots.some((r) => pathname === r || pathname.startsWith(`${r}/`));

const WIDTH = "mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-10 min-[1800px]:max-w-[1600px]";

export function AppFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useSession();
  const auth = useAuthMode();
  const authPage = under(pathname, AUTH_PAGES);
  const infoPage = under(pathname, INFO_PAGES);
  const bare = authPage || infoPage;

  // Without a session, wait for /health to say whether sign-in is required. If /health cannot
  // be reached, show the page anyway: its own requests will report the outage.
  const needsLogin = !bare && !session && auth.mode === "accounts";
  const blocked = !bare && !session && (auth.status === "loading" || needsLogin);

  useEffect(() => {
    if (!needsLogin) return;
    const here = window.location.pathname + window.location.search;
    router.replace(here === "/" ? "/login" : `/login?next=${encodeURIComponent(here)}`);
  }, [needsLogin, pathname, router]);

  const showNav = !bare && !blocked;

  // The same element tree in every frame, so moving between pages only changes classes and
  // the page itself is not remounted.
  return (
    <>
      {showNav && <Nav />}
      <div className={`flex min-h-dvh flex-col ${showNav ? "lg:pl-64" : ""}`}>
        {infoPage && <InfoBar />}
        <main
          id="main"
          className={authPage ? "flex w-full flex-1 flex-col" : `${WIDTH} flex-1 py-6 sm:py-8`}
        >
          {blocked ? <FrameLoading /> : children}
        </main>
        <Footer className={WIDTH} />
      </div>
    </>
  );
}

/** Shown instead of an app page while the session is checked or the redirect runs. */
export function FrameLoading() {
  const t = useT(frameMessages);
  return (
    <div className="flex items-center justify-center py-24">
      <Loading label={t("checkingSession")} />
    </div>
  );
}

/** Top bar of the info pages: brand, language and a way into the app. */
function InfoBar() {
  const t = useT(frameMessages);
  const session = useSession();
  const auth = useAuthMode();
  const signIn = !session && auth.mode === "accounts";
  return (
    <header className="border-b border-border bg-sidebar/90 backdrop-blur">
      <div className={`${WIDTH} flex h-14 items-center justify-between gap-3`}>
        <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
          <Logo className="size-8" />
          <span className="text-[17px]">Kasa</span>
        </Link>
        <div className="flex items-center gap-2">
          <LanguageSwitch />
          <Link
            href={signIn ? "/login" : "/"}
            className="inline-flex h-8 items-center rounded-lg bg-accent px-3 text-sm font-medium text-accent-foreground shadow-card hover:brightness-110"
          >
            {signIn ? t("signIn") : t("openKasa")}
          </Link>
        </div>
      </div>
    </header>
  );
}
