"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CircleCheck, Sparkles, TriangleAlert } from "lucide-react";
import { Alert, Button, Card, CardTitle, Field, PageHeader, inputStyles } from "@/components/ui";
import { api, type Customer, type ParsedCommand } from "@/lib/api";
import { cn, formatCurrency, formatDate } from "@/lib/utils";

const DEMO_COMMAND = "Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.";

function Detail({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-content-muted">{label}</dt>
      <dd className={cn("mt-0.5 text-sm", muted ? "text-content-muted" : "text-content")}>
        {value}
      </dd>
    </div>
  );
}

export default function NewInvoicePage() {
  const router = useRouter();
  const [command, setCommand] = useState(DEMO_COMMAND);
  const [parsed, setParsed] = useState<ParsedCommand | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const redirectRef = useRef<ReturnType<typeof setTimeout>>();

  // The success path navigates on a timer; clear it if the user leaves first.
  useEffect(() => () => clearTimeout(redirectRef.current), []);

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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't parse that command. Try rephrasing it.");
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
      setSuccess(`${invoice.invoice_number} created. Opening it now…`);
      redirectRef.current = setTimeout(() => router.push(`/invoices/${invoice.id}`), 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't create the invoice.");
      setCreating(false);
    }
  }

  const lowConfidence = parsed !== null && parsed.confidence < 0.7;

  return (
    <div className="rise mx-auto max-w-2xl space-y-6">
      <PageHeader
        title="Collect payment"
        description="Describe the invoice in plain English. SettleFlow extracts the details for you to confirm."
      />

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
            rows={3}
            className={cn(inputStyles, "resize-y")}
          />
        </Field>

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={handleParse} loading={loading} disabled={!command.trim()}>
            {loading ? "Reading…" : "Parse command"}
          </Button>
          {command !== DEMO_COMMAND && (
            <Button variant="quiet" size="sm" onClick={() => setCommand(DEMO_COMMAND)}>
              Use the example
            </Button>
          )}
        </div>

        {/*
         * States the boundary plainly: the parser reads text and stops there.
         * Nothing here can move money or contact anyone.
         */}
        <p className="flex items-start gap-2 border-t border-line pt-4 text-xs text-content-muted">
          <Sparkles aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Parsing only reads your text into fields. Nothing is sent and no payment is requested
          until you create the invoice.
        </p>
      </Card>

      {parsed && (
        <Card className="space-y-5 p-6">
          <div className="flex items-center justify-between gap-4">
            <CardTitle>Confirm the details</CardTitle>
            <span
              className={cn(
                "tabular text-xs",
                lowConfidence ? "text-pending" : "text-content-muted"
              )}
            >
              {(parsed.confidence * 100).toFixed(0)}% confident
            </span>
          </div>

          <dl className="grid gap-4 sm:grid-cols-2">
            <Detail label="Customer" value={parsed.customer_name} />
            <Detail label="Amount" value={formatCurrency(parsed.amount, parsed.currency)} />
            <Detail label="Description" value={parsed.description} />
            <Detail label="Due date" value={formatDate(parsed.due_date)} />
          </dl>

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
            <div className="flex items-start gap-2.5 rounded-lg border border-paid/40 bg-paid-tint/60 p-3 text-sm text-paid">
              <CircleCheck aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Matched <span className="font-medium">{customer.name}</span>
                {customer.company && ` · ${customer.company}`}
                <span className="block opacity-90">{customer.email}</span>
              </span>
            </div>
          ) : (
            <div className="flex items-start gap-2.5 rounded-lg border border-pending/40 bg-pending-tint/60 p-3 text-sm text-pending">
              <TriangleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                No customer matches &ldquo;{parsed.customer_name}&rdquo;. Add them to your
                directory or check the spelling, then parse again.
              </span>
            </div>
          )}

          <Button onClick={handleCreate} loading={creating} disabled={!customer || !!success}>
            {creating ? "Creating…" : "Create invoice"}
          </Button>
        </Card>
      )}

      {error && <Alert tone="error">{error}</Alert>}
      {success && <Alert tone="success">{success}</Alert>}
    </div>
  );
}
