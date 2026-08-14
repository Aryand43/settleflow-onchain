"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, FileText, SearchX, WifiOff } from "lucide-react";
import { ChatPanel } from "@/components/ChatPanel";
import { StatusBadge } from "@/components/StatusBadge";
import { Button, Card, EmptyState, Skeleton, inputStyles } from "@/components/ui";
import { api, type Invoice } from "@/lib/api";
import { cn, daysUntil, formatCurrency, formatDate, formatDueRelative } from "@/lib/utils";

const statusFilters = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "paid", label: "Paid" },
  { value: "overdue", label: "Overdue" },
];

function DueCell({ invoice }: { invoice: Invoice }) {
  const late = invoice.status !== "paid" && daysUntil(invoice.due_date) < 0;
  return (
    <>
      <span className={cn("tabular", late ? "text-overdue" : "text-content-secondary")}>
        {formatDate(invoice.due_date)}
      </span>
      {invoice.status !== "paid" && (
        <span className="block text-xs text-content-muted">
          {formatDueRelative(invoice.due_date)}
        </span>
      )}
    </>
  );
}

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .invoices()
      .then(setInvoices)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Request failed"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return invoices.filter((inv) => {
      const matchesSearch =
        !q ||
        inv.invoice_number.toLowerCase().includes(q) ||
        (inv.customer_name || "").toLowerCase().includes(q) ||
        inv.description.toLowerCase().includes(q);
      return matchesSearch && (statusFilter === "all" || inv.status === statusFilter);
    });
  }, [invoices, search, statusFilter]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-44" />
        <Skeleton className="h-10 w-full max-w-md" />
        <Card className="divide-y divide-line">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center justify-between gap-4 px-4 py-4">
              <Skeleton className="h-5 w-28" />
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-6 w-20 rounded" />
            </div>
          ))}
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rise mx-auto max-w-md py-12 text-center">
        <WifiOff aria-hidden className="mx-auto h-6 w-6 text-content-muted" />
        <h1 className="mt-4 text-lg font-medium text-content">Couldn&rsquo;t load invoices</h1>
        <p className="mt-1.5 break-words font-mono text-xs text-content-muted">{error}</p>
        <Button className="mt-5" onClick={load}>
          Retry
        </Button>
      </div>
    );
  }

  const isFiltered = search.trim() !== "" || statusFilter !== "all";

  return (
    <div className="rise space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-content">Invoices</h1>
          <p className="mt-2 max-w-xl text-sm text-content-muted">
            The collection queue — who owes you, who is late, and what has already settled.
          </p>
        </div>
        <Link
          href="/invoices/new"
          className="inline-flex items-center rounded bg-accent px-4 py-2 text-sm font-medium text-accent-on transition-colors duration-150 hover:bg-accent-hover"
        >
          Collect payment
        </Link>
      </div>

      {invoices.length > 0 && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1 sm:max-w-xs">
            <label htmlFor="invoice-search" className="sr-only">
              Search invoices
            </label>
            <input
              id="invoice-search"
              type="search"
              placeholder="Search number, customer, or work"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className={inputStyles}
            />
          </div>
          <div
            role="group"
            aria-label="Filter by status"
            className="flex flex-wrap gap-1 rounded border border-line p-1"
          >
            {statusFilters.map((opt) => {
              const active = statusFilter === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setStatusFilter(opt.value)}
                  className={cn(
                    "rounded px-3 py-1.5 text-xs font-medium transition-colors duration-150",
                    active
                      ? "bg-surface-raised text-content"
                      : "text-content-muted hover:text-content"
                  )}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {invoices.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No invoices yet"
          description="Describe a job in plain English and SettleFlow turns it into an invoice with a payment link."
          action={
            <Link
              href="/invoices/new"
              className="inline-flex items-center rounded bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-hover"
            >
              Collect payment
            </Link>
          }
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No matching invoices"
          description={
            isFiltered
              ? "No invoice matches your search and filter. Try a different term or clear the filter."
              : "Nothing to show."
          }
          action={
            <Button
              variant="secondary"
              onClick={() => {
                setSearch("");
                setStatusFilter("all");
              }}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <>
          <Card className="divide-y divide-line md:hidden">
            {filtered.map((inv) => (
              <Link
                key={inv.id}
                href={`/invoices/${inv.id}`}
                className="flex items-start justify-between gap-3 px-4 py-3.5 transition-colors duration-150 hover:bg-surface-raised"
              >
                <div className="min-w-0">
                  <p className="font-mono text-sm font-medium text-content">{inv.invoice_number}</p>
                  <p className="truncate text-sm text-content-secondary">{inv.customer_name}</p>
                  <p className="tabular mt-1 font-mono text-sm text-content">
                    {formatCurrency(inv.amount, inv.currency)}
                  </p>
                  <p className="mt-0.5 text-xs text-content-muted">
                    <DueCell invoice={inv} />
                  </p>
                </div>
                <StatusBadge status={inv.status} />
              </Link>
            ))}
          </Card>

          <Card className="hidden overflow-hidden md:block">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-surface-raised text-xs text-content-muted">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Invoice</th>
                  <th scope="col" className="px-4 py-3 font-medium">Customer</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Amount</th>
                  <th scope="col" className="px-4 py-3 font-medium">Due</th>
                  <th scope="col" className="px-4 py-3 font-medium">Status</th>
                  <th scope="col" className="w-10 px-4 py-3">
                    <span className="sr-only">View</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {filtered.map((inv) => (
                  <tr key={inv.id} className="group transition-colors duration-150 hover:bg-surface-raised">
                    <td className="px-4 py-3">
                      <Link
                        href={`/invoices/${inv.id}`}
                        className="font-mono font-medium text-content hover:text-accent-text"
                      >
                        {inv.invoice_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-content-secondary">{inv.customer_name}</td>
                    <td className="tabular px-4 py-3 text-right font-mono text-content">
                      {formatCurrency(inv.amount, inv.currency)}
                    </td>
                    <td className="px-4 py-3">
                      <DueCell invoice={inv} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={inv.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <ChevronRight
                        aria-hidden
                        className="h-4 w-4 text-content-muted transition-colors duration-150 group-hover:text-content"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}

      <ChatPanel
        scope="payments"
        inputId="payments-chat"
        suggestions={[
          "Which invoices are unpaid?",
          "Did INV-0002 settle on-chain?",
          "What's overdue for Marcus Koh?",
        ]}
      />
    </div>
  );
}
