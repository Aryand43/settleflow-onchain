"use client";

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { CircleCheck, Clock, Loader2, MessageCircle, TriangleAlert, Wallet } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { Button, CopyButton, inputStyles } from "@/components/ui";
import { api, type NegotiationMessage, type PaymentPage } from "@/lib/api";
import { cn, daysUntil, formatCurrency, formatDate } from "@/lib/utils";

export default function PayPage({ params }: { params: { token: string } }) {
  const [data, setData] = useState<PaymentPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<NegotiationMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);

  useEffect(() => {
    api
      .paymentPage(params.token)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Request failed"))
      .finally(() => setLoading(false));
    api
      .paymentPageMessages(params.token)
      .then(setMessages)
      .catch(() => {});
  }, [params.token]);

  async function handleSend() {
    if (!draft.trim()) return;
    setSending(true);
    try {
      await api.sendPaymentPageMessage(params.token, draft.trim());
      setDraft("");
      const updated = await api.paymentPageMessages(params.token);
      setMessages(updated);
      const refreshed = await api.paymentPage(params.token);
      setData(refreshed);
    } catch {
      // Best-effort: leave the draft in place so the customer can retry.
    } finally {
      setSending(false);
    }
  }

  async function handlePay() {
    setPaying(true);
    setPayError(null);
    try {
      // On-chain settlement is three sequential transactions, so this holds
      // for a couple of seconds. The button's loading state carries it.
      const result = await api.payByToken(params.token);
      setData(result.payment_page);
    } catch (e) {
      setPayError(
        e instanceof Error ? e.message : "That didn't go through. Try again in a moment."
      );
    } finally {
      setPaying(false);
    }
  }

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
          <p className="mb-5 rounded border border-pending/30 bg-pending-tint/50 px-4 py-2.5 text-center text-xs text-pending">
            Testnet demo — no real funds will be collected.
          </p>
        )}

        <div className="overflow-hidden rounded border border-line bg-surface shadow-lifted">
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
              <div className="flex items-start gap-3 rounded border border-paid/40 bg-paid-tint/50 p-4">
                <CircleCheck aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-paid" />
                <div className="text-sm text-paid">
                  <p className="font-medium">Payment received</p>
                  <p className="mt-0.5 opacity-90">
                    Settlement was confirmed on-chain. Nothing further is owed.
                  </p>
                </div>
              </div>
            ) : closed ? (
              <div className="flex items-start gap-3 rounded border border-line-strong p-4 text-sm text-content-secondary">
                <TriangleAlert aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-content-muted" />
                <div>
                  <p className="font-medium text-content">This invoice was cancelled</p>
                  <p className="mt-0.5 text-content-muted">No payment is required.</p>
                </div>
              </div>
            ) : (
              <>
                {/*
                 * The QR and link ARE the real payment mechanism — no
                 * wallet-connect flow is wired, so they stay the primary path.
                 * The button below is explicitly the demo's stand-in wallet,
                 * labelled as such; a CTA that pretended to be the real thing
                 * would be a lie.
                 */}
                <p className="text-sm font-medium text-content">
                  Pay in {data.currency} from your wallet
                </p>
                <p className="mt-1 text-sm text-content-muted">
                  Scan this code with a wallet app, or copy the link to open it on another device.
                </p>

                <div className="mt-5 flex flex-col items-center gap-4">
                  <div className="rounded bg-white p-4">
                    <QRCodeSVG value={data.payment_url} size={168} />
                  </div>
                  <CopyButton value={data.payment_url} label="Copy payment link" />
                </div>

                {data.demo_mode && (
                  <div className="mt-6 border-t border-dashed border-line-strong pt-5">
                    <p className="text-xs uppercase tracking-wide text-content-muted">
                      Demo shortcut
                    </p>
                    <p className="mt-1 text-xs text-content-muted">
                      {data.chain_configured
                        ? "Pays this invoice from the demo wallet, so you don't need a funded wallet to try it. It signs a real transaction on the testnet."
                        : "Marks this invoice paid so you can try the flow. No transaction is broadcast."}
                    </p>
                    {payError && <p className="mt-2 text-xs text-overdue">{payError}</p>}
                    <Button
                      variant="demo"
                      size="sm"
                      className="mt-3 w-full"
                      onClick={handlePay}
                      loading={paying}
                      disabled={paying}
                    >
                      <Wallet aria-hidden className="h-4 w-4" />
                      Pay {formatCurrency(data.amount, data.currency)} with the demo wallet
                    </Button>
                  </div>
                )}

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

          {!paid && !closed && (
            <div className="border-t border-line px-6 py-6 sm:px-7">
              <p className="flex items-center gap-2 text-sm font-medium text-content">
                <MessageCircle aria-hidden className="h-4 w-4 text-content-muted" />
                Need more time or want to arrange a payment plan?
              </p>
              <p className="mt-1 text-xs text-content-muted">
                A short note here goes straight to SettleFlow&rsquo;s collections agent, not a person &mdash;
                it can grant a short extension itself, or flag anything bigger for the merchant.
              </p>

              {messages.length > 0 && (
                <ul className="mt-4 space-y-2.5">
                  {messages.map((m) => (
                    <li
                      key={m.id}
                      className={cn(
                        "max-w-[85%] rounded px-3 py-2 text-sm",
                        m.sender === "customer"
                          ? "ml-auto bg-accent/10 text-content"
                          : "bg-surface-sunken text-content-secondary"
                      )}
                    >
                      {m.message}
                    </li>
                  ))}
                </ul>
              )}

              <div className="mt-4 flex gap-2">
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSend();
                  }}
                  placeholder="e.g. Can I get 5 more days?"
                  className={inputStyles}
                />
                <Button size="md" loading={sending} disabled={!draft.trim()} onClick={handleSend}>
                  Send
                </Button>
              </div>
            </div>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-content-muted">
          Sent with SettleFlow · {data.invoice_number}
        </p>
      </div>
    </div>
  );
}
