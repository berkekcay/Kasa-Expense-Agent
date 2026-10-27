import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { Footer } from "@/components/Footer";
import { LocaleRoot } from "@/components/LocaleRoot";
import { Nav } from "@/components/Nav";
import { ToastProvider } from "@/components/Toast";
import { LOCALE_SCRIPT } from "@/lib/i18n";
import { THEME_SCRIPT } from "@/lib/theme";
import "./globals.css";

const inter = Inter({ subsets: ["latin", "latin-ext"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Kasa", template: "%s · Kasa" },
  description: "AI money assistant for students and shared flats.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f6f8" },
    { media: "(prefers-color-scheme: dark)", color: "#0b0c0f" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // data-theme is set before paint by THEME_SCRIPT when the user picked light or dark.
    <html lang="en" className={`h-full antialiased ${inter.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT + LOCALE_SCRIPT }} />
      </head>
      <body className="min-h-full font-sans">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[60] focus:rounded-md focus:bg-card focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <ToastProvider>
          <LocaleRoot>
            <Nav />
            <div className="flex min-h-dvh flex-col lg:pl-64">
              <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-10 min-[1800px]:max-w-[1600px]">
                {children}
              </main>
              <Footer className="mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-10 min-[1800px]:max-w-[1600px]" />
            </div>
          </LocaleRoot>
        </ToastProvider>
      </body>
    </html>
  );
}
