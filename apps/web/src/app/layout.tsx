import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Container } from "@/components/container";
import { HeaderNav, MobileNav } from "@/components/site-nav";

export const metadata: Metadata = {
  title: "PricePilot — Autonomous AI Shopping Agent",
  description:
    "Tell PricePilot what you want to buy and it researches products, compares stores, analyzes prices and reviews, and gives an explainable recommendation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
          <Container className="flex h-14 items-center gap-6">
            <Link href="/" className="text-lg font-bold tracking-tight">
              PricePilot
            </Link>
            <HeaderNav />
          </Container>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t py-6 text-center text-xs text-muted-foreground">
          <Container>
            PricePilot — prices and offers shown here come from real public providers
            (e.g. OpenFoodFacts) where available. Unavailable providers are shown as
            such; no data is fabricated.
          </Container>
        </footer>
        <MobileNav />
      </body>
    </html>
  );
}