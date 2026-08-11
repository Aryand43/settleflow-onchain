"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { ArrowLeft, BellRing, ExternalLink, FastForward, Send, Wallet } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import {
  Alert,
  Button,
  Card,
  CardTitle,
  CopyButton,
  PageHeader,
  Skeleton,
} from "@/components/ui";
import { explorerTxUrl } from "@/lib/contracts";
import { api, DEMO_MODE, type ActivityEvent, type Invoice } from "@/lib/api";
import { formatCurrency, formatDate, formatDateTime, formatDueRelative, truncateHash } from "@/lib/utils";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5">
      <dt className="shrink-0 text-sm text-content-muted">{label}</dt>
      <dd className="min-w-0 text-right text-sm text-content">{children}</dd>
    </div>
  );
}

export default function InvoiceDetailPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [inv, act] = await Promise.all([api.invoice(id), api.invoiceActivity(id)]);
      setInvoice(inv);
      setActivity(act);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (Number.isInteger(id) && id > 0) {
      load();
    } else {
      setError("That invoice id isn't valid.");
      setLoading(false);
    }
  }, [id, load]);

  async function runAction(name: string, fn: () => Promise<unknown>) {
    setActionLoading(name);
    setMessage(null);
    setError(null);
    try {
      const result = await fn();
      if (result && typeof result === "object" && "message" in result) {
        setMessage((result as { message: string }).message);
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActionLoading(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-9 w-40" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-96 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="rise mx-auto max-w-md py-12 text-center">
        <h1 className="text-lg font-medium text-content">Invoice not available</h1>
        <p className="mt-1.5 text-sm text-content-muted">
          {error ?? "This invoice doesn't exist or was removed."}
        </p>
        <Link
          href="/invoices"
          className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-accent-text hover:underline"
        >
          <ArrowLeft aria-hidden className="h-4 w-4" />
          Back to invoices
        </Link>
      </div>
    );
  }

  const isPaid = invoice.status === "paid";
  const txUrl = invoice.blockchain_tx_hash ? explorerTxUrl(invoice.blockchain_tx_hash) : null;

  return (
    <div className="rise space-y-6">
      <div>
        <Link
          href="/invoices"
          className="inline-flex items-center gap-1.5 text-sm text-content-muted transition-colors duration-150 hover:text-content"
        >
          <ArrowLeft aria-hidden className="h-4 w-4" />
          Back to invoices
        </Link>
        <div className="mt-3">
          <PageHeader
            title={invoice.invoice_number}
            description={invoice.description}
            action={<StatusBadge status={invoice.status} />}
          />
        </div>
      </div>

      {message && <Alert tone="success">{message}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <CardTitle>Invoice details</CardTitle>
          <dl className="mt-3 divide-y divide-line">
            <Row label="Customer">{invoice.customer_name}</Row>
            <Row label="Amount">
              <span className="tabular font-medium">
                {formatCurrency(invoice.amount, invoice.currency)}
              </span>
            </Row>
            <Row label="Due date">
              <span className="tabular">{formatDate(invoice.due_date)}</span>
              {!isPaid && (
                <span className="block text-xs text-content-muted">
                  {formatDueRelative(invoice.due_date)}
                </span>
              )}
            </Row>
            <Row label="Reminders sent">
              <span className="tabular">{invoice.reminder_count}</span>
            </Row>
            {invoice.blockchain_tx_hash && (
              <Row label="Transaction">
                <span className="inline-flex items-center gap-2">
                  <span
                    title={invoice.blockchain_tx_hash}
                    className="tabular font-mono text-xs text-paid"
                  >
                    {truncateHash(invoice.blockchain_tx_hash)}
                  </span>
                  <CopyButton value={invoice.blockchain_tx_hash} label="Copy" />
                  {txUrl && (
                    <a
                      href={txUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent-text hover:text-content"
                    >
                      <ExternalLink aria-hidden className="h-3.5 w-3.5" />
                      <span className="sr-only">View transaction on the block explorer</span>
                    </a>
                  )}
                </span>
              </Row>
            )}
          </dl>

          {invoice.payment_url && (
            <div className="mt-5 border-t border-line pt-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-content-muted">Payment link</p>
                <CopyButton value={invoice.payment_url} label="Copy link" />
              </div>
              <a
                href={invoice.payment_url}
                target="_blank"
                rel="noreferrer"
                className="mt-2 block break-all text-sm text-accent-text hover:underline"
              >
                {invoice.payment_url}
              </a>
              <div className="mt-4 flex flex-col items-center gap-2">
                {/* QR needs a light quiet zone to scan reliably. */}
                <div className="rounded-xl bg-white p-3">
                  <QRCodeSVG value={invoice.payment_url} size={128} />
                </div>
                <p className="text-xs text-content-muted">Scan to open the payment page</p>
              </div>
            </div>
          )}
        </Card>

        <div className="space-y-6">
          <Card className="p-6">
            <CardTitle>Actions</CardTitle>

            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => runAction("send", () => api.sendInvoice(id))}
                loading={actionLoading === "send"}
                disabled={!!actionLoading}
              >
                <Send aria-hidden className="h-4 w-4" />
                Send invoice email
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => runAction("reminder", () => api.sendReminder(id))}
                loading={actionLoading === "reminder"}
                disabled={!!actionLoading || isPaid}
              >
                <BellRing aria-hidden className="h-4 w-4" />
                Send reminder
              </Button>
            </div>

            {/*
             * Demo controls are fenced off from the real actions above. They
             * stand in for events the product would otherwise learn from the
             * chain, so they must never look like a button that moves money.
             */}
            {DEMO_MODE && (
              <div className="mt-5 border-t border-dashed border-line-strong pt-4">
                <p className="text-xs uppercase tracking-wide text-content-muted">
                  Demo controls
                </p>
                <p className="mt-1 text-xs text-content-muted">
                  Simulated locally. No transaction is broadcast.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    variant="demo"
                    size="sm"
                    onClick={() => runAction("time", () => api.simulateTime(id))}
                    loading={actionLoading === "time"}
                    disabled={!!actionLoading || isPaid}
                  >
                    <FastForward aria-hidden className="h-4 w-4" />
                    Simulate time
                  </Button>
                  <Button
                    variant="demo"
                    size="sm"
                    onClick={() => runAction("pay", () => api.simulatePayment(id))}
                    loading={actionLoading === "pay"}
                    disabled={!!actionLoading || isPaid}
                  >
                    <Wallet aria-hidden className="h-4 w-4" />
                    Simulate payment
                  </Button>
                </div>
              </div>
            )}

            {isPaid && (
              <p className="mt-4 text-xs text-content-muted">
                This invoice is settled. Reminders and simulations are disabled.
              </p>
            )}
          </Card>

          <Card className="p-6">
            <CardTitle>Activity timeline</CardTitle>
            {activity.length === 0 ? (
              <p className="mt-4 text-sm text-content-muted">
                Nothing has happened on this invoice yet.
              </p>
            ) : (
              <ol className="mt-4">
                {activity.map((event, i) => (
                  <li key={event.id} className="relative flex gap-3 pb-5 last:pb-0">
                    {/* Hairline rail plus a node, rather than a heavy colored edge. */}
                    {i < activity.length - 1 && (
                      <span
                        aria-hidden
                        className="absolute left-[3px] top-3 h-full w-px bg-line"
                      />
                    )}
                    <span
                      aria-hidden
                      className="relative mt-1.5 h-[7px] w-[7px] shrink-0 rounded-full bg-content-muted"
                    />
                    <div className="min-w-0">
                      <p className="text-sm text-content-secondary">{event.message}</p>
                      <p className="tabular mt-0.5 text-xs text-content-muted">
                        {formatDateTime(event.created_at)}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
