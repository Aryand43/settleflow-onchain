"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import {
  ArrowLeft,
  BellRing,
  ExternalLink,
  FastForward,
  MessageCircle,
  ScanSearch,
  Send,
  Wallet,
} from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import {
  Alert,
  Button,
  Card,
  CopyButton,
  DemoNotice,
  Skeleton,
} from "@/components/ui";
import { explorerTxUrl } from "@/lib/contracts";
import { api, DEMO_MODE, type ActivityEvent, type Invoice, type NegotiationMessage } from "@/lib/api";
import {
  activityLabel,
  activityLane,
  cn,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatDueRelative,
  truncateHash,
} from "@/lib/utils";

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
  const [negotiation, setNegotiation] = useState<NegotiationMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [inv, act, neg] = await Promise.all([
        api.invoice(id),
        api.invoiceActivity(id),
        api.invoiceMessages(id),
      ]);
      setInvoice(inv);
      setActivity(act);
      setNegotiation(neg);
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
          <Skeleton className="h-96 rounded" />
          <Skeleton className="h-96 rounded" />
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
        <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-mono text-3xl font-semibold tracking-tight text-content">
              {invoice.invoice_number}
            </h1>
            <p className="mt-2 max-w-xl text-sm text-content-muted">{invoice.description}</p>
          </div>
          <StatusBadge status={invoice.status} size="large" />
        </div>
        <p aria-live="polite" className="sr-only">
          Invoice {invoice.invoice_number} is {invoice.status}
        </p>
      </div>

      {message && <Alert tone="success">{message}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-lg font-medium tracking-tight text-content">Invoice details</h2>
          <dl className="mt-3 divide-y divide-line">
            <Row label="Customer">{invoice.customer_name}</Row>
            <Row label="Amount">
              <span className="tabular font-mono font-medium">
                {formatCurrency(invoice.amount, invoice.currency)}
              </span>
            </Row>
            <Row label="Due date">
              <span className="tabular font-mono">{formatDate(invoice.due_date)}</span>
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
                    className="tabular font-mono text-xs text-chain"
                  >
                    {truncateHash(invoice.blockchain_tx_hash)}
                  </span>
                  <CopyButton value={invoice.blockchain_tx_hash} label="Copy" />
                  {txUrl && (
                    <a
                      href={txUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-chain hover:text-content"
                    >
                      <ExternalLink aria-hidden className="h-3.5 w-3.5" />
                      <span className="sr-only">View transaction on the block explorer</span>
                    </a>
                  )}
                </span>
              </Row>
            )}
          </dl>
        </Card>

        <Card className="p-6">
          <h2 className="text-lg font-medium tracking-tight text-content">Share payment</h2>
          <p className="mt-1 text-sm text-content-muted">
            Testnet only. The customer pays from this link; SettleFlow does not mark it paid.
          </p>

          {invoice.payment_url ? (
            <div className="mt-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-content-muted">Payment link</p>
                <CopyButton value={invoice.payment_url} label="Copy link" />
              </div>
              <a
                href={invoice.payment_url}
                target="_blank"
                rel="noreferrer"
                className="mt-2 block break-all font-mono text-xs text-accent-text hover:underline"
              >
                {invoice.payment_url}
              </a>
              <div className="mt-4 flex flex-col items-center gap-2">
                <div className="rounded bg-white p-3">
                  <QRCodeSVG value={invoice.payment_url} size={128} />
                </div>
                <p className="text-xs text-content-muted">Scan to open the payment page</p>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-content-muted">No payment link on this invoice yet.</p>
          )}

          <div className="mt-5 flex flex-wrap gap-2 border-t border-line pt-4">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => runAction("send", () => api.sendInvoice(id))}
              loading={actionLoading === "send"}
              disabled={!!actionLoading}
            >
              <Send aria-hidden className="h-4 w-4" />
              Send email preview
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
        </Card>
      </div>

      <Card className="p-6">
        <h2 className="text-lg font-medium tracking-tight text-content">Evidence</h2>
        <p className="mt-1 text-sm text-content-muted">
          Chain events are marked in cyan. Paid status only changes after InvoicePaid is observed.
        </p>
        {activity.length === 0 ? (
          <p className="mt-4 text-sm text-content-muted">
            Nothing has happened on this invoice yet.
          </p>
        ) : (
          <ol className="mt-5">
            {activity.map((event, i) => {
              const lane = activityLane(event.event_type);
              const chain = lane === "chain";
              return (
                <li key={event.id} className="relative flex gap-3 pb-5 last:pb-0">
                  {i < activity.length - 1 && (
                    <span
                      aria-hidden
                      className="absolute left-[3px] top-3 h-full w-px bg-line"
                    />
                  )}
                  <span
                    aria-hidden
                    className={cn(
                      "relative mt-1.5 h-[7px] w-[7px] shrink-0 rounded-full",
                      chain ? "bg-chain" : "bg-content-muted"
                    )}
                  />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <span
                        className={cn(
                          "text-[11px] font-medium uppercase tracking-wide",
                          chain ? "text-chain" : "text-content-muted"
                        )}
                      >
                        {activityLabel(event.event_type)}
                      </span>
                      <span className="text-[11px] text-content-muted">{lane}</span>
                    </div>
                    <p className={cn("mt-0.5 text-sm", chain ? "font-mono text-xs text-chain" : "text-content-secondary")}>
                      {event.message}
                    </p>
                    <p className="tabular mt-0.5 text-xs text-content-muted">
                      {formatDateTime(event.created_at)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </Card>

      {negotiation.length > 0 && (
        <Card className="p-6">
          <h2 className="text-lg font-medium tracking-tight text-content">
            <span className="inline-flex items-center gap-2">
              <MessageCircle aria-hidden className="h-4 w-4 text-content-muted" />
              Negotiation
            </span>
          </h2>
          <p className="mt-1 text-xs text-content-muted">
            What the customer asked for, and how the collections agent responded — automatically,
            and only ever within its allowed bounds.
          </p>
          <ul className="mt-4 space-y-2.5">
            {negotiation.map((m) => (
              <li
                key={m.id}
                className={cn(
                  "max-w-[85%] rounded px-3 py-2 text-sm",
                  m.sender === "customer"
                    ? "bg-surface-sunken text-content"
                    : "ml-auto bg-accent/10 text-content-secondary"
                )}
              >
                <p>{m.message}</p>
                <p className="mt-1 text-[11px] uppercase tracking-wide text-content-muted">
                  {m.sender === "customer" ? "Customer" : "Agent"}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {DEMO_MODE ? (
        <DemoNotice title="Demo controls">
          <p className="mb-4 text-sm text-content-secondary">
            Simulate payment mints test USDC, approves the router, and calls payInvoice on the
            configured chain. Status flips to paid only after an InvoicePaid event is observed.
            Simulate time advances the due date locally so reminder rules can fire. Scan
            blockchain reads events that have already been emitted.
          </p>
          <div className="flex flex-wrap gap-2">
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
              onClick={() => runAction("scan", () => api.scanBlockchain())}
              loading={actionLoading === "scan"}
              disabled={!!actionLoading}
            >
              <ScanSearch aria-hidden className="h-4 w-4" />
              Scan blockchain
            </Button>
          </div>
          {isPaid && (
            <p className="mt-3 text-xs text-content-muted">
              This invoice is settled. Reminders and payment simulation are disabled.
            </p>
          )}
        </DemoNotice>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => runAction("scan", () => api.scanBlockchain())}
            loading={actionLoading === "scan"}
            disabled={!!actionLoading}
          >
            <ScanSearch aria-hidden className="h-4 w-4" />
            Scan blockchain
          </Button>
        </div>
      )}
    </div>
  );
}
