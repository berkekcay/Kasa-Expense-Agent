import type { MetadataRoute } from "next";
import { SITE_URL } from "@/features/info/site";

// Only the public info pages are worth indexing; everything else is the signed in app.
// SITE_URL comes from NEXT_PUBLIC_SITE_URL, which must be set at deploy time.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: ["/about", "/help", "/privacy", "/terms", "/cookies"],
      disallow: [
        "/budgets",
        "/chat",
        "/expenses",
        "/houses",
        "/import",
        "/inbox",
        "/receipts",
        "/settings",
        "/subscriptions",
      ],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
