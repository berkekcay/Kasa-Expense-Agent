"use client";

// When the app opens (also right after signing in), ask the server to check the connected
// mailbox. The server decides whether it is due (one check every few minutes) and does
// nothing without a mailbox. New purchases update the inbox count and show a toast.

import { useEffect } from "react";
import { api } from "@/lib/api";
import { dataChanged } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useToast } from "@/components/Toast";
import { mailMessages } from "@/features/settings/mailMessages";

const KEY = "kasa.mailAutoCheck";
const EVERY_MS = 15 * 60 * 1000;
let running = false; // one request at a time, across remounts

function lastCheck(user: string): number {
  try {
    return Number(sessionStorage.getItem(`${KEY}.${user}`)) || 0;
  } catch {
    return 0;
  }
}

function markChecked(user: string) {
  try {
    sessionStorage.setItem(`${KEY}.${user}`, String(Date.now()));
  } catch {
    // private mode: the server's own limit still applies
  }
}

/** `user` is whoever is signed in; null while signed out or before the session is known. */
export function useAutoMailCheck(user: string | null) {
  const notify = useToast();
  const t = useT(mailMessages);

  useEffect(() => {
    if (!user || running || Date.now() - lastCheck(user) < EVERY_MS) return;
    running = true;
    markChecked(user);
    api.integrations
      .mailAutoSync()
      .then(({ result }) => {
        if (result && result.created > 0) {
          dataChanged("inbox");
          notify(t("autoFound", { n: result.created }), "success");
        }
      })
      .catch(() => {
        // a background nicety: errors show up when the user checks by hand in Settings
      })
      .finally(() => {
        running = false;
      });
  }, [user, notify, t]);
}
