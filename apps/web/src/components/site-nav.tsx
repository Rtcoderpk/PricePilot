"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/search", label: "Search" },
  { href: "/compare", label: "Compare" },
  { href: "/track", label: "Track" },
  { href: "/history", label: "History" },
  { href: "/alerts", label: "Alerts" },
  { href: "/shopping", label: "AI assistant" },
];

/** Primary links surfaced on mobile (keep the tab bar short). */
const MOBILE_ITEMS = [
  { href: "/search", label: "Search" },
  { href: "/shopping", label: "Assistant" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/track", label: "Track" },
  { href: "/alerts", label: "Alerts" },
  { href: "/settings", label: "Settings" },
];

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === href; // exact only
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function HeaderNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary" className="ml-auto hidden items-center gap-1 md:flex">
      {NAV_ITEMS.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded-md px-2.5 py-1.5 text-sm transition-colors",
              active ? "bg-secondary font-medium text-foreground" : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
            )}
          >
            {item.label}
          </Link>
        );
      })}
      <Link
        href="/settings"
        aria-current={pathname === "/settings" ? "page" : undefined}
        className={cn(
          "rounded-md px-2.5 py-1.5 text-sm transition-colors",
          pathname === "/settings"
            ? "bg-secondary font-medium text-foreground"
            : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
        )}
      >
        Settings
      </Link>
    </nav>
  );
}

/** Bottom tab bar — visible on small screens only. */
export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 md:hidden"
    >
      <ul className="mx-auto flex max-w-6xl items-stretch justify-between px-2 pb-[env(safe-area-inset-bottom)]">
        {MOBILE_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium transition-colors",
                  active ? "text-primary" : "text-muted-foreground",
                )}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}