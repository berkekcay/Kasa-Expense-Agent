// Links and dates shared by the footer, the info pages and the legal pages.

export const REPO_URL = "https://github.com/berkekcay/Kasa-Expense-Agent";
export const ISSUES_URL = `${REPO_URL}/issues`;
export const NEW_ISSUE_URL = `${REPO_URL}/issues/new`;
/** Issue #13: "delete my account and data". */
export const DELETE_ISSUE_URL = `${REPO_URL}/issues/13`;

/**
 * Public address of the web app. Set NEXT_PUBLIC_SITE_URL at deploy time (for example the
 * Cloud Run URL of kasa-web). The fallback is a placeholder, not a real site.
 */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://kasa.example.com").replace(/\/+$/, "");

/** Last update of the privacy, terms and cookie texts. */
export const LEGAL_UPDATED = { en: "27 October 2026", tr: "27 Ekim 2026" } as const;
