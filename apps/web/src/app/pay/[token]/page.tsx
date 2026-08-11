"use client";

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { CircleCheck, Clock, Loader2, TriangleAlert } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { CopyButton } from "@/components/ui";
import { api, type PaymentPage } from "@/lib/api";
import { daysUntil, formatCurrency, formatDate } from "@/lib/utils";

export default function PayPage({ params }: { params: { token: string } }) {
  const [data, setData] = useState<PaymentPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .paymentPage(params.token)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Request failed"))
      .finally(() => setLoading(false));
  }, [params.token]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <Loader2 aria-hidden className="h-5 w-5 animate-spin text-content-muted" />
        <span className="sr-only">Loading payment details</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
        <div className="max-w-sm text-center">
          <TriangleAlert aria-hidden className="mx-auto h-6 w-6 text-content-muted" />
          <h1 className="mt-4 text-lg font-medium text-content">This link isn&rsquo;t valid</h1>
          <p className="mt-1.5 text-sm text-content-muted">
            The payment link may have expired or been mistyped. Ask the sender for a new one.
          </p>
        </div>
      </div>
    );
  }

  const paid = data.status === "paid";
  const closed = data.status === "cancelled";
  const late = !paid && !closed && daysUntil(data.due_date) < 0;

  return (
    <div className="min-h-screen bg-canvas px-4 py-10 text-content sm:py-16">
      <div className="rise mx-auto max-w-md">
        {data.demo_mode && (
          <p className="mb-5 rounded-lg border border-pending/30 bg-pending-tint/50 px-4 py-2.5 text-center text-xs text-pending">
            Testnet demo — no real funds will be collected.
          </p>
        )}

        <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-lifted">
          <div className="border-b border-line px-6 py-5 sm:px-7">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm text-content-muted">Invoice from</p>
                <p className="truncate font-medium text-content">{data.merchant_name}</p>
              </div>
              <StatusBadge status={data.status} />
            </div>
          </div>

          <div className="px-6 py-6 sm:px-7">
            {/* The one number this page exists to communicate. */}
            <p className="text-sm text-content-muted">Amount due</p>
            <p className="tabular mt-1 text-4xl font-semibold tracking-tight text-content">
              {formatCurrency(data.amount, data.currency)}
            </p>
            <p className="mt-2 text-sm text-content-muted">
              <span className={late ? "text-overdue" : undefined}>
                {paid ? "Paid" : `Due ${formatDate(data.due_date)}`}
              </span>
              {" · "}
              {data.invoice_number}
            </p>

            <dl className="mt-6 space-y-3 border-t border-line pt-5 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-content-muted">Billed to</dt>
                <dd className="text-right text-content">{data.customer_name}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="shrink-0 text-content-muted">For</dt>
                <dd className="text-right text-content">{data.description}</dd>
              </div>
            </dl>
          </div>

          <div className="border-t border-line bg-surface-sunken px-6 py-6 sm:px-7">
            {paid ? (
              <div className="flex items-start gap-3 rounded-lg border border-paid/40 bg-paid-tint/50 p-4">
                <CircleCheck aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-paid" />
                <div className="text-sm text-paid">
                  <p className="font-medium">Payment received</p>
                  <p className="mt-0.5 opacity-90">
                    Settlement was confirmed on-chain. Nothing further is owed.
                  </p>
                </div>
              </div>
            ) : closed ? (
              <div className="flex items-start gap-3 rounded-lg border border-line-strong p-4 text-sm text-content-secondary">
                <TriangleAlert aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-content-muted" />
                <div>
                  <p className="font-medium text-content">This invoice was cancelled</p>
                  <p className="mt-0.5 text-content-muted">No payment is required.</p>
                </div>
              </div>
            ) : (
              <>
                {/*
                 * The QR and link ARE the payment mechanism, so they lead here
                 * rather than sitting under a button. No wallet-connect flow is
                 * wired yet, and a CTA that opens an alert would be a lie.
                 */}
                <p className="text-sm font-medium text-content">
                  Pay in {data.currency} from your wallet
                </p>
                <p className="mt-1 text-sm text-content-muted">
                  Scan this code with a wallet app, or copy the link to open it on another device.
                </p>

                <div className="mt-5 flex flex-col items-center gap-4">
                  <div className="rounded-xl bg-white p-4">
                    <QRCodeSVG value={data.payment_url} size={168} />
                  </div>
                  <CopyButton value={data.payment_url} label="Copy payment link" />
                </div>

                <div className="mt-6 flex items-start gap-2.5 border-t border-line pt-5 text-xs text-content-muted">
                  <Clock aria-hidden className="mt-px h-3.5 w-3.5 shrink-0" />
                  <p>
                    {data.chain_configured
                      ? "This page updates automatically once the transfer is confirmed on-chain. You don't need to notify the sender."
                      : "On-chain settlement isn't switched on for this demo invoice, so the status here won't change on its own."}
                  </p>
                </div>
              </>
            )}
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-content-muted">
          Sent with SettleFlow · {data.invoice_number}
        </p>
      </div>
    </div>
  );
}
