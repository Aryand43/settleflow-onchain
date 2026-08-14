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

  if (pathname.startsWith("/pay")) {
    return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
  }

  return (
    <MotionConfig reducedMotion="user">
    <div className="flex min-h-screen bg-canvas text-content">
      <aside className="hidden w-[13.5rem] shrink-0 flex-col border-r border-line bg-surface md:flex">
        <Link href="/" className="flex items-center gap-3 px-4 py-5">
          <span
            aria-hidden
            className="flex h-8 w-8 items-center justify-center rounded bg-accent font-mono text-xs font-bold text-accent-on"
          >
            SF
          </span>
          <span className="text-sm font-semibold tracking-tight">SettleFlow</span>
        </Link>

        <nav aria-label="Main" className="flex-1 space-y-0.5 px-2">
          {nav.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 rounded px-3 py-2 text-sm font-medium transition-colors duration-150",
                  active
                    ? "bg-surface-raised text-content"
                    : "text-content-muted hover:bg-surface-raised hover:text-content"
                )}
              >
                <item.icon aria-hidden className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="m-3 rounded border border-dashed border-overdue/40 bg-overdue-tint/40 px-3 py-3">
          <p className="eyebrow text-overdue">Testnet demo</p>
          <p className="mt-1 text-xs text-content-muted">No real funds</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 border-b border-line bg-canvas/90 backdrop-blur">
          <div className="flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <Link href="/" className="flex items-center gap-2 md:hidden">
                <span
                  aria-hidden
                  className="flex h-8 w-8 items-center justify-center rounded bg-accent font-mono text-xs font-bold text-accent-on"
                >
                  SF
                </span>
              </Link>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-content">Demo Merchant</p>
                <p className="text-xs text-content-muted">Demo workspace</p>
              </div>
              <span className="shrink-0 rounded border border-overdue/40 bg-overdue-tint px-2 py-0.5 text-[11px] text-overdue">
                Testnet
              </span>
            </div>
            <Link
              href="/invoices/new"
              className="inline-flex shrink-0 items-center gap-2 rounded bg-accent px-3 py-2 text-sm font-medium text-accent-on transition-colors duration-150 hover:bg-accent-hover"
            >
              <Plus aria-hidden className="h-4 w-4" />
              <span className="hidden sm:inline">Collect payment</span>
              <span className="sr-only sm:hidden">Collect payment</span>
            </Link>
          </div>
        </header>

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 sm:py-8">{children}</main>

        <nav
          aria-label="Main"
          className="sticky bottom-0 border-t border-line bg-canvas/95 backdrop-blur md:hidden"
        >
          <ul className="flex">
            {nav.map((item) => {
              const active = pathname === item.href;
              return (
                <li key={item.href} className="flex-1">
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex flex-col items-center gap-1 px-2 py-2.5 text-[11px] font-medium",
                      active ? "text-content" : "text-content-muted"
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
      </div>
    </div>
    </MotionConfig>
  );
}
