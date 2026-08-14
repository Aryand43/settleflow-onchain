"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MotionConfig } from "framer-motion";
import { FileText, LayoutDashboard, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/invoices", label: "Invoices", icon: FileText },
  { href: "/invoices/new", label: "Collect payment", icon: Plus },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // The payer surface is deliberately shell-free: no nav, no merchant chrome.
  if (pathname.startsWith("/pay")) {
    return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-screen flex-col bg-canvas text-content">
        <header className="sticky top-0 z-10 border-b border-line bg-canvas/85 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
            <Link href="/" className="flex items-center gap-3 rounded-lg">
              <span
                aria-hidden
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-sm font-bold text-accent-on"
              >
                SF
              </span>
              <span className="min-w-0">
                <span className="block text-base font-semibold tracking-tight text-content">
                  SettleFlow
                </span>
                <span className="hidden text-xs text-content-muted sm:block">
                  Automated stablecoin invoicing
                </span>
              </span>
            </Link>

            <Link
              href="/invoices/new"
              className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-on transition-colors duration-150 hover:bg-accent-hover sm:px-4"
            >
              <Plus aria-hidden className="h-4 w-4" />
              <span className="hidden sm:inline">Collect payment</span>
              <span className="sr-only sm:hidden">Collect payment</span>
            </Link>
          </div>

          {/* Mobile nav — the sidebar below is md and up only. */}
          <nav aria-label="Main" className="overflow-x-auto border-t border-line px-4 md:hidden">
            <ul className="flex min-w-max gap-1 py-1.5">
              {nav.map((item) => {
                const active = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150",
                        active
                          ? "bg-surface-raised text-content"
                          : "text-content-muted hover:text-content"
                      )}
                    >
                      <item.icon aria-hidden className="h-4 w-4" />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        </header>

        <div className="mx-auto flex w-full max-w-7xl flex-1 gap-8 px-4 py-6 sm:px-6 sm:py-8">
          <aside className="hidden w-48 shrink-0 md:block">
            <nav aria-label="Main" className="sticky top-24 space-y-1">
              {nav.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150",
                      active
                        ? "bg-surface-raised text-content"
                        : "text-content-muted hover:bg-surface hover:text-content"
                    )}
                  >
                    <item.icon aria-hidden className="h-4 w-4 shrink-0" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </aside>

          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </div>
    </MotionConfig>
  );
}
