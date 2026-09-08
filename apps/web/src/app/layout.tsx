import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "PricePilot — Autonomous AI Shopping Agent",
  description:
    "Tell PricePilot what you want to buy and it researches products, compares stores, analyzes prices and reviews, and gives an explainable recommendation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <header className="border-b">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
            <Link href="/" className="text-lg font-bold tracking-tight">
              PricePilot
            </Link>
            <nav className="ml-auto flex items-center gap-4 text-sm text-muted-foreground">
              <Link href="/dashboard" className="hover:text-foreground">
                Dashboard
              </Link>
              <Link href="/search" className="hover:text-foreground">
                Search
              </Link>
              <Link href="/compare" className="hover:text-foreground">
                Compare
              </Link>
              <Link href="/track" className="hover:text-foreground">
                Track
              </Link>
              <Link href="/history" className="hover:text-foreground">
                History
              </Link>
              <Link href="/alerts" className="hover:text-foreground">
                Alerts
              </Link>
              <Link href="/settings" className="hover:text-foreground">
                Settings
              </Link>
              <Link href="/shopping" className="hover:text-foreground">
                AI assistant
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t py-6 text-center text-xs text-muted-foreground">
          <div className="mx-auto max-w-6xl px-4">
            PricePilot — prices and offers shown here come from real public providers
            (e.g. OpenFoodFacts) where available. Unavailable providers are shown as
            such; no data is fabricated.
          </div>
        </footer>
      </body>
    </html>
  );
}