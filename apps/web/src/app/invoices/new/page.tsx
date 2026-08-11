"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Customer, type ParsedCommand } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";

const DEMO_COMMAND =
  "Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.";

export default function NewInvoicePage() {
  const router = useRouter();
  const [command, setCommand] = useState(DEMO_COMMAND);
  const [parsed, setParsed] = useState<ParsedCommand | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleParse() {
    setLoading(true);
    setError(null);
    setParsed(null);
    setCustomer(null);
    try {
      const result = await api.parseCommand(command);
      setParsed(result);
      const customers = await api.customers();
      const match = customers.find(
        (c) =>
          c.name.toLowerCase() === result.customer_name.toLowerCase() ||
          c.name.toLowerCase().includes(result.customer_name.toLowerCase())
      );
      setCustomer(match || null);
      if (!match) {
        setError(`No customer match for "${result.customer_name}". Add them first or check spelling.`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Parse failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!parsed || !customer) return;
    setCreating(true);
    setError(null);
    try {
      const invoice = await api.createInvoice({
        customer_id: customer.id,
        amount: parsed.amount,
        currency: parsed.currency,
        description: parsed.description,
        due_date: parsed.due_date,
      });
      await api.sendInvoice(invoice.id);
      setSuccess(`Invoice ${invoice.invoice_number} created and email preview generated.`);
      setTimeout(() => router.push(`/invoices/${invoice.id}`), 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Collect payment</h1>
        <p className="mt-1 text-slate-400">
          Describe the invoice in plain English. SettleFlow extracts the details.
        </p>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 space-y-4">
        <label className="block text-sm font-medium text-slate-300">Natural language command</label>
        <textarea
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-500"
        />
        <button
          onClick={handleParse}
          disabled={loading || !command.trim()}
          className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600 disabled:opacity-50"
        >
          {loading ? "Parsing..." : "Parse command"}
        </button>
      </div>

      {parsed && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 space-y-4">
          <h2 className="text-lg font-medium text-white">Extracted invoice</h2>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-slate-500">Customer</dt>
              <dd className="text-white">{parsed.customer_name}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Amount</dt>
              <dd className="text-white">{formatCurrency(parsed.amount, parsed.currency)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Description</dt>
              <dd className="text-white">{parsed.description}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Due date</dt>
              <dd className="text-white">{formatDate(parsed.due_date)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Confidence</dt>
              <dd className="text-white">{(parsed.confidence * 100).toFixed(0)}%</dd>
            </div>
          </dl>

          {customer ? (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">
              Matched customer: {customer.name} ({customer.email}) — {customer.company}
            </div>
          ) : (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
              No customer match found.
            </div>
          )}

          <button
            onClick={handleCreate}
            disabled={creating || !customer}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create invoice"}
          </button>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>
      )}
      {success && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200">
          {success}
        </div>
      )}
    </div>
  );
}
