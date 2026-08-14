"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CircleCheck, Sparkles, TriangleAlert, UserPlus } from "lucide-react";
import {
  Alert,
  Button,
  Card,
  CardTitle,
  Field,
  PageHeader,
  Skeleton,
  inputStyles,
} from "@/components/ui";
import { api, type Customer, type ParsedCommand } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { cn, formatCurrency, formatDate } from "@/lib/utils";

const DEMO_COMMAND = "Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.";

/*
 * Finds every customer a parsed name could mean.
 *
 * An exact name always wins outright, even against a substring that happens to
 * sort earlier. Otherwise this returns ALL partial matches rather than the
 * first one: "Marcus" with both a Marcus Koh and a Marcus Watney in the
 * directory used to silently invoice whichever sorted first, which is exactly
 * the kind of mistake you only notice after the client gets the email.
 */
function matchCustomers(name: string, list: Customer[]): Customer[] {
  const q = name.trim().toLowerCase();
  if (!q) return [];

  const exact = list.filter((c) => c.name.toLowerCase() === q);
  if (exact.length) return exact;

  return list.filter((c) => c.name.toLowerCase().includes(q));
}

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
  const { user } = useRequireAuth();
  const [command, setCommand] = useState(DEMO_COMMAND);
  const [parsed, setParsed] = useState<ParsedCommand | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [candidates, setCandidates] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [quickAddEmail, setQuickAddEmail] = useState("");
  const [quickAdding, setQuickAdding] = useState(false);
  const redirectRef = useRef<ReturnType<typeof setTimeout>>();

  // The success path navigates on a timer; clear it if the user leaves first.
  useEffect(() => () => clearTimeout(redirectRef.current), []);

  async function handleParse() {
    setLoading(true);
    setError(null);
    setParsed(null);
    setCustomer(null);
    setCandidates([]);
    setQuickAddEmail("");
    try {
      const result = await api.parseCommand(command);
      setParsed(result);
      const customers = await api.customers();
      const matches = matchCustomers(result.customer_name, customers);
      setCandidates(matches);
      // Only auto-select when there is exactly one answer. Two matches is a
      // question for the merchant, not a coin flip.
      setCustomer(matches.length === 1 ? matches[0] : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't parse that command. Try rephrasing it.");
    } finally {
      setLoading(false);
    }
  }

  /*
   * Before this existed, an unrecognised name was a dead end: the page told you
   * to add the customer to your directory and gave you nowhere to do it, and
   * the create button stayed disabled. Now the name is already known — only the
   * email is missing.
   */
  async function handleQuickAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!parsed) return;
    setQuickAdding(true);
    setError(null);
    try {
      const created = await api.createCustomer({
        name: parsed.customer_name,
        email: quickAddEmail.trim(),
      });
      setCustomer(created);
      setCandidates([created]);
      setQuickAddEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add that customer");
    } finally {
      setQuickAdding(false);
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

  if (!user) return <Skeleton className="h-64 w-full" />;

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
            <div className="flex items-start gap-2.5 rounded border border-paid/40 bg-paid-tint/60 p-3 text-sm text-paid">
              <CircleCheck aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Matched <span className="font-medium">{customer.name}</span>
                {customer.company && ` · ${customer.company}`}
                <span className="block opacity-90">{customer.email}</span>
                {candidates.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setCustomer(null)}
                    className="mt-1 block underline underline-offset-2 opacity-90 hover:opacity-100"
                  >
                    Not this one? Pick again
                  </button>
                )}
              </span>
            </div>
          ) : candidates.length > 1 ? (
            /*
             * More than one customer fits the name. Guessing here means the
             * invoice, the payment link, and every reminder go to the wrong
             * client — so it asks instead.
             */
            <div className="rounded border border-pending/40 bg-pending-tint/60 p-3">
              <div className="flex items-start gap-2.5 text-sm text-pending">
                <TriangleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  {candidates.length} customers match &ldquo;{parsed.customer_name}&rdquo;. Which
                  one are you invoicing?
                </span>
              </div>

              <ul className="mt-3 space-y-1.5">
                {candidates.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => setCustomer(c)}
                      className="flex w-full items-center justify-between gap-3 rounded border border-line bg-surface px-3 py-2 text-left text-sm transition-colors duration-150 hover:border-content-muted hover:bg-surface-raised"
                    >
                      <span className="min-w-0">
                        <span className="block font-medium text-content">
                          {c.name}
                          {c.company && (
                            <span className="font-normal text-content-muted"> · {c.company}</span>
                          )}
                        </span>
                        <span className="block truncate text-xs text-content-muted">{c.email}</span>
                      </span>
                      <span className="shrink-0 text-xs text-content-muted">Select</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="rounded border border-pending/40 bg-pending-tint/60 p-3">
              <div className="flex items-start gap-2.5 text-sm text-pending">
                <TriangleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  &ldquo;{parsed.customer_name}&rdquo; isn&rsquo;t in your directory yet. Add an
                  email and they&rsquo;re in &mdash; or{" "}
                  <Link href="/customers" className="underline underline-offset-2">
                    manage customers
                  </Link>{" "}
                  if the spelling is off.
                </span>
              </div>

              <form onSubmit={handleQuickAdd} className="mt-3 flex flex-wrap gap-2">
                <input
                  type="email"
                  required
                  value={quickAddEmail}
                  onChange={(e) => setQuickAddEmail(e.target.value)}
                  placeholder={`Email for ${parsed.customer_name}`}
                  className={cn(inputStyles, "min-w-0 flex-1")}
                />
                <Button
                  type="submit"
                  variant="secondary"
                  loading={quickAdding}
                  disabled={!quickAddEmail.trim()}
                >
                  <UserPlus aria-hidden className="h-4 w-4" />
                  Add
                </Button>
              </form>
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
