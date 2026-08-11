"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { api, DEMO_MODE, type ActivityEvent, type Invoice } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { formatCurrency, formatDate } from "@/lib/utils";

export default function InvoiceDetailPage({ params }: { params: { id: string } }) {
  const id = parseInt(params.id, 10);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [inv, act] = await Promise.all([api.invoice(id), api.invoiceActivity(id)]);
      setInvoice(inv);
      setActivity(act);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

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

  if (loading) return <div className="text-slate-400">Loading invoice...</div>;
  if (error && !invoice) {
    return <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">{error}</div>;
  }
  if (!invoice) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/invoices" className="text-sm text-blue-400 hover:underline">
            ← Back to invoices
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-white">{invoice.invoice_number}</h1>
          <p className="mt-1 text-slate-400">{invoice.description}</p>
        </div>
        <StatusBadge status={invoice.status} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 space-y-4">
          <h2 className="text-lg font-medium text-white">Invoice details</h2>
          <dl className="grid gap-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Customer</dt>
              <dd className="text-white">{invoice.customer_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Amount</dt>
              <dd className="text-white">{formatCurrency(invoice.amount, invoice.currency)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Due date</dt>
              <dd className="text-white">{formatDate(invoice.due_date)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Reminders sent</dt>
              <dd className="text-white">{invoice.reminder_count}</dd>
            </div>
            {invoice.blockchain_tx_hash && (
              <div>
                <dt className="text-slate-500">Transaction</dt>
                <dd className="mt-1 break-all font-mono text-xs text-emerald-400">
                  {invoice.blockchain_tx_hash}
                </dd>
              </div>
            )}
          </dl>

          {invoice.payment_url && (
            <div className="pt-4 border-t border-slate-800">
              <p className="text-sm text-slate-500 mb-2">Payment link</p>
              <a
                href={invoice.payment_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-blue-400 break-all hover:underline"
              >
                {invoice.payment_url}
              </a>
              <div className="mt-4 flex justify-center rounded-lg bg-white p-4">
                <QRCodeSVG value={invoice.payment_url} size={128} />
              </div>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 space-y-3">
            <h2 className="text-lg font-medium text-white">Actions</h2>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => runAction("send", () => api.sendInvoice(id))}
                disabled={!!actionLoading}
                className="rounded-lg bg-slate-700 px-3 py-2 text-sm text-white hover:bg-slate-600 disabled:opacity-50"
              >
                Send invoice email
              </button>
              <button
                onClick={() => runAction("reminder", () => api.sendReminder(id))}
                disabled={!!actionLoading || invoice.status === "paid"}
                className="rounded-lg bg-slate-700 px-3 py-2 text-sm text-white hover:bg-slate-600 disabled:opacity-50"
              >
                Send reminder
              </button>
              <button
                onClick={() => runAction("time", () => api.simulateTime(id))}
                disabled={!!actionLoading || invoice.status === "paid"}
                className="rounded-lg bg-amber-600 px-3 py-2 text-sm text-white hover:bg-amber-500 disabled:opacity-50"
              >
                Simulate time
              </button>
              {DEMO_MODE && invoice.status !== "paid" && (
                <button
                  onClick={() => runAction("pay", () => api.simulatePayment(id))}
                  disabled={!!actionLoading}
                  className="rounded-lg bg-emerald-600 px-3 py-2 text-sm text-white hover:bg-emerald-500 disabled:opacity-50"
                >
                  Simulate payment
                </button>
              )}
            </div>
            {message && <p className="text-sm text-emerald-300">{message}</p>}
            {error && <p className="text-sm text-red-300">{error}</p>}
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
            <h2 className="mb-4 text-lg font-medium text-white">Activity timeline</h2>
            {activity.length === 0 ? (
              <p className="text-sm text-slate-500">No activity yet.</p>
            ) : (
              <ul className="space-y-4">
                {activity.map((event) => (
                  <li key={event.id} className="border-l-2 border-blue-600 pl-4">
                    <p className="text-sm text-slate-200">{event.message}</p>
                    <p className="text-xs text-slate-500">
                      {event.event_type} · {formatDate(event.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
