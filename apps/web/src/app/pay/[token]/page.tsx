"use client";

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { api, DEMO_MODE, type PaymentPage } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { formatCurrency, formatDate } from "@/lib/utils";

export default function PayPage({ params }: { params: { token: string } }) {
  const [data, setData] = useState<PaymentPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);
  const [paid, setPaid] = useState(false);

  useEffect(() => {
    api
      .paymentPage(params.token)
      .then((page) => {
        setData(page);
        setPaid(page.status === "paid");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [params.token]);

  async function handleSimulatePay() {
    if (!DEMO_MODE) return;
    setPaying(true);
    // For public pay page, user would normally use wallet; demo uses merchant simulate from detail page
    // Show instruction for prototype
    setPaying(false);
    alert(
      "For the demo, open the merchant dashboard invoice detail and click 'Simulate payment', or connect a testnet wallet when configured."
    );
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
        Loading payment details...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6">
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-8 text-center text-red-200">
          {error || "Invoice not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-12 text-slate-100">
      <div className="mx-auto max-w-lg">
        {data.demo_mode && (
          <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-center text-sm text-amber-200">
            Testnet demo — no real funds will be collected.
          </div>
        )}

        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-8 shadow-xl">
          <div className="mb-6 flex items-start justify-between">
            <div>
              <p className="text-sm text-slate-400">{data.merchant_name}</p>
              <h1 className="mt-1 text-2xl font-semibold text-white">{data.invoice_number}</h1>
            </div>
            <StatusBadge status={data.status} />
          </div>

          <div className="space-y-4 border-b border-slate-800 pb-6">
            <div>
              <p className="text-sm text-slate-500">Bill to</p>
              <p className="text-white">{data.customer_name}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Description</p>
              <p className="text-white">{data.description}</p>
            </div>
            <div className="flex justify-between">
              <div>
                <p className="text-sm text-slate-500">Amount due</p>
                <p className="text-3xl font-semibold text-white">
                  {formatCurrency(data.amount, data.currency)}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-slate-500">Due date</p>
                <p className="text-white">{formatDate(data.due_date)}</p>
              </div>
            </div>
          </div>

          <div className="mt-6 flex flex-col items-center gap-4">
            <div className="rounded-xl bg-white p-4">
              <QRCodeSVG value={data.payment_url} size={160} />
            </div>
            <p className="text-center text-xs text-slate-500">Scan to pay on mobile</p>
          </div>

          <div className="mt-8 space-y-3">
            {paid ? (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-center text-emerald-200">
                Payment received. Thank you!
              </div>
            ) : (
              <>
                <button
                  disabled={paying || data.status === "paid"}
                  className="w-full rounded-lg bg-blue-600 py-3 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                  onClick={handleSimulatePay}
                >
                  {data.chain_configured ? "Connect wallet & pay" : "Pay with testnet wallet"}
                </button>
                {DEMO_MODE && (
                  <p className="text-center text-xs text-slate-500">
                    Demo mode: merchant can simulate payment from the invoice detail page.
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
