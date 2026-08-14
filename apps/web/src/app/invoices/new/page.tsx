"use client";

import { useState } from "react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { CircleCheck, Sparkles, TriangleAlert } from "lucide-react";
import { Alert, Button, Card, CopyButton, Field, inputStyles } from "@/components/ui";
import { api, type Customer, type Invoice, type ParsedCommand } from "@/lib/api";
import { cn, formatCurrency, formatDate } from "@/lib/utils";

const DEMO_COMMAND = "Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.";

function matchCustomer(name: string, list: Customer[]) {
  const q = name.trim().toLowerCase();
  if (!q) return null;
  return (
    list.find((c) => c.name.toLowerCase() === q) ||
    list.find((c) => c.name.toLowerCase().includes(q)) ||
    null
  );
}

export default function NewInvoicePage() {
  const [command, setCommand] = useState(DEMO_COMMAND);
  const [parsed, setParsed] = useState<ParsedCommand | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Invoice | null>(null);
  const [sendPreview, setSendPreview] = useState<string | null>(null);

  async function handleParse() {
    setLoading(true);
    setError(null);
    setParsed(null);
    setCustomer(null);
    setCreated(null);
    setSendPreview(null);
    try {
      const result = await api.parseCommand(command);
      setParsed(result);
      const list = await api.customers();
      setCustomers(list);
      setCustomer(matchCustomer(result.customer_name, list));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't parse that command. Try rephrasing it.");
    } finally {
      setLoading(false);
    }
  }

  function updateParsed(patch: Partial<ParsedCommand>) {
    if (!parsed) return;
    const next = { ...parsed, ...patch };
    setParsed(next);
    if (patch.customer_name !== undefined) {
      setCustomer(matchCustomer(patch.customer_name, customers));
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
      try {
        const sent = await api.sendInvoice(invoice.id);
        setSendPreview(sent.message);
      } catch {
        setSendPreview(null);
      }
      setCreated(invoice);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't create the invoice.");
    } finally {
      setCreating(false);
    }
  }

  function reset() {
    setParsed(null);
    setCustomer(null);
    setCreated(null);
    setSendPreview(null);
    setError(null);
    setCommand(DEMO_COMMAND);
  }

  const lowConfidence = parsed !== null && parsed.confidence < 0.7;

  if (created) {
    return (
      <div className="rise mx-auto max-w-2xl space-y-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-content">Invoice created</h1>
          <p className="mt-2 text-sm text-content-muted">
            Ready to collect. Status stays pending until the chain confirms payment.
          </p>
        </div>

        <Card className="space-y-5 p-6">
          <div>
            <p className="text-sm text-content-muted">Invoice</p>
            <p className="mt-1 font-mono text-2xl font-medium tracking-tight text-content">
              {created.invoice_number}
            </p>
            <p className="tabular mt-2 font-mono text-lg text-content">
              {formatCurrency(created.amount, created.currency)}
            </p>
            <p className="mt-1 text-sm text-content-secondary">
              {created.customer_name} · due {formatDate(created.due_date)}
            </p>
          </div>

          {created.payment_url && (
            <div className="border-t border-line pt-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-content-muted">Payment link</p>
                <CopyButton value={created.payment_url} label="Copy link" />
              </div>
              <a
                href={created.payment_url}
                target="_blank"
                rel="noreferrer"
                className="mt-2 block break-all font-mono text-xs text-accent-text hover:underline"
              >
                {created.payment_url}
              </a>
              <div className="mt-4 flex flex-col items-center gap-2">
                <div className="rounded bg-white p-3">
                  <QRCodeSVG value={created.payment_url} size={128} />
                </div>
                <p className="text-xs text-content-muted">Scan to open the payment page</p>
              </div>
            </div>
          )}

          {sendPreview && (
            <Alert tone="info" title="Email preview written">
              {sendPreview} No email is sent in this demo — open the preview file to see what the
              customer would receive.
            </Alert>
          )}

          <div className="flex flex-wrap gap-2">
            <Link
              href={`/invoices/${created.id}`}
              className="inline-flex items-center rounded bg-accent px-4 py-2 text-sm font-medium text-accent-on transition-colors duration-150 hover:bg-accent-hover"
            >
              View invoice
            </Link>
            <Button variant="secondary" onClick={reset}>
              Create another
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="rise mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-content">Collect payment</h1>
        <p className="mt-2 max-w-xl text-sm text-content-muted">
          Type the invoice in one sentence. AI only converts text into fields — nothing is sent and
          no payment is requested until you create it.
        </p>
      </div>

      <Card className="space-y-4 p-6">
        <Field
          label="What are you invoicing for?"
          htmlFor="command"
          hint="Include the customer, amount, currency, what the work was, and when it's due."
        >
          <textarea
            id="command"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            rows={4}
            className={cn(inputStyles, "min-h-[7rem] resize-y font-sans text-base leading-relaxed")}
          />
        </Field>

        <p className="rounded border border-line bg-surface-sunken px-3 py-2 font-mono text-xs text-content-muted">
          Example: {DEMO_COMMAND}
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={handleParse} loading={loading} disabled={!command.trim()}>
            {loading ? "Reading the sentence" : "Parse command"}
          </Button>
          {command !== DEMO_COMMAND && (
            <Button variant="quiet" size="sm" onClick={() => setCommand(DEMO_COMMAND)}>
              Use the example
            </Button>
          )}
        </div>

        <p className="flex items-start gap-2 border-t border-line pt-4 text-xs text-content-muted">
          <Sparkles aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {loading
            ? "Reading the sentence. No payment action is being taken."
            : "Parsing only reads your text into fields. Nothing is sent and no payment is requested until you create the invoice."}
        </p>
      </Card>

      {parsed && (
        <Card className="space-y-5 p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-medium tracking-tight text-content">Confirm the details</h2>
              <p className="mt-1 text-sm text-content-muted">
                This step only converts text into invoice fields.
              </p>
            </div>
            <span
              className={cn(
                "tabular shrink-0 text-xs",
                lowConfidence ? "text-pending" : "text-content-muted"
              )}
            >
              {(parsed.confidence * 100).toFixed(0)}% confident
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Customer" htmlFor="parsed-customer">
              <input
                id="parsed-customer"
                value={parsed.customer_name}
                onChange={(e) => updateParsed({ customer_name: e.target.value })}
                className={inputStyles}
              />
            </Field>
            <Field label="Amount" htmlFor="parsed-amount">
              <input
                id="parsed-amount"
                type="number"
                min={0}
                step="0.01"
                value={parsed.amount}
                onChange={(e) => updateParsed({ amount: Number(e.target.value) })}
                className={cn(inputStyles, "font-mono")}
              />
            </Field>
            <Field label="Currency" htmlFor="parsed-currency">
              <input
                id="parsed-currency"
                value={parsed.currency}
                onChange={(e) => updateParsed({ currency: e.target.value })}
                className={cn(inputStyles, "font-mono")}
              />
            </Field>
            <Field label="Due date" htmlFor="parsed-due">
              <input
                id="parsed-due"
                type="date"
                value={parsed.due_date.slice(0, 10)}
                onChange={(e) => updateParsed({ due_date: e.target.value })}
                className={cn(inputStyles, "font-mono")}
              />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Description" htmlFor="parsed-description">
                <input
                  id="parsed-description"
                  value={parsed.description}
                  onChange={(e) => updateParsed({ description: e.target.value })}
                  className={inputStyles}
                />
              </Field>
            </div>
          </div>

          {parsed.missing_fields.length > 0 && (
            <Alert tone="warning" title="Some details were guessed">
              Couldn&rsquo;t find {parsed.missing_fields.join(", ")} in your command. Check the
              values above before creating.
            </Alert>
          )}

          {lowConfidence && parsed.missing_fields.length === 0 && (
            <Alert tone="warning">
              Low confidence in this reading. Double-check the amount and due date.
            </Alert>
          )}

          {customer ? (
            <div className="flex items-start gap-2.5 rounded border border-paid/40 bg-paid-tint/60 p-3 text-sm text-paid">
              <CircleCheck aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Matched <span className="font-medium">{customer.name}</span>
                {customer.company && ` · ${customer.company}`}
                <span className="block opacity-90">{customer.email}</span>
              </span>
            </div>
          ) : (
            <div className="flex items-start gap-2.5 rounded border border-pending/40 bg-pending-tint/60 p-3 text-sm text-pending">
              <TriangleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                No customer matches &ldquo;{parsed.customer_name}&rdquo;. Add them to your
                directory or check the spelling, then parse again.
              </span>
            </div>
          )}

          <Button onClick={handleCreate} loading={creating} disabled={!customer}>
            {creating ? "Creating…" : "Create invoice"}
          </Button>
        </Card>
      )}

      {error && <Alert tone="error">{error}</Alert>}
    </div>
  );
}
