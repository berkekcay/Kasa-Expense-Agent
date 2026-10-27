import type { Metadata, Viewport } from "next";
import { Nav } from "@/components/Nav";
import { ToastProvider } from "@/components/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Kasa", template: "%s · Kasa" },
  description: "AI money assistant for students and shared flats.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#16161a" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col font-sans">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <ToastProvider>
          <Nav />
          <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:py-8 2xl:max-w-7xl">
            {children}
          </main>
        </ToastProvider>
      </body>
    </html>
  );
}
