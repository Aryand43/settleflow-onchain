"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Inbox, Sparkles, WifiOff } from "lucide-react";
import { CollectionChart } from "@/components/CollectionChart";
import { Alert, Button, Card, CardTitle, PageHeader, Skeleton } from "@/components/ui";
import { api, type ActivityEvent, type CollectionsAgentResult, type DashboardSummary } from "@/lib/api";
import { cn, formatCurrency, formatDateTime } from "@/lib/utils";

const TIER_LABEL: Record<string, string> = {
  friendly: "Friendly nudge",
  firm: "Firm follow-up",
  final: "Final notice",
};

const DEMO_COMMAND = "Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.";

function Stat({
  label,
  value,
  sub,
  emphasis,
}: {
  label: string;
  value: string;
  sub?: string;
  emphasis?: "overdue" | "paid";
}) {
  return (
    <div className="px-5 py-4">
      <p className="text-sm text-content-muted">{label}</p>
      <p
        className={cn(
          "tabular mt-1 text-2xl font-semibold tracking-tight",
          emphasis === "overdue" && "text-overdue",
          emphasis === "paid" && "text-paid",
          !emphasis && "text-content"
        )}
      >
        {value}
      </p>
      <p className="mt-0.5 text-xs text-content-muted">{sub ?? " "}</p>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      <div>
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mt-2 h-4 w-72" />
      </div>
      <Card className="grid grid-cols-2 divide-line lg:grid-cols-4 lg:divide-x">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="px-5 py-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-2 h-7 w-28" />
            <Skeleton className="mt-1.5 h-3 w-20" />
          </div>
        ))}
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-[22rem] rounded-xl" />
        <Skeleton className="h-[22rem] rounded-xl" />
      </div>
    </div>
  );
}

export default function OverviewPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentResult, setAgentResult] = useState<CollectionsAgentResult | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([api.dashboard(), api.activity()])
      .then(([s, a]) => {
        setSummary(s);
        setActivity(a);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Request failed"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const runAgent = useCallback(() => {
    setAgentRunning(true);
    api
      .runCollectionsAgent()
      .then((result) => {
        setAgentResult(result);
        load();
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Request failed"))
      .finally(() => setAgentRunning(false));
  }, [load]);

  if (loading) return <DashboardSkeleton />;

  if (error || !summary) {
    return (
      <div className="rise mx-auto max-w-md py-12 text-center">
        <WifiOff aria-hidden className="mx-auto h-6 w-6 text-content-muted" />
        <h1 className="mt-4 text-lg font-medium text-content">Can&rsquo;t reach the API</h1>
        <p className="mt-1.5 text-sm text-content-muted">
          Start the backend on port 8000, then try again.
        </p>
        {error && (
          <p className="mt-3 break-words font-mono text-xs text-content-muted">{error}</p>
        )}
        <Button className="mt-5" onClick={load}>
          Retry
        </Button>
      </div>
    );
  }

  const hasOverdue = summary.total_overdue > 0;

  return (
    <div className="rise space-y-8">
      <PageHeader
        title="Overview"
        description="Track collections across your stablecoin invoices."
      />

      {/*
       * One grouped panel rather than four floating cards: these figures are
       * read together, and dividing them keeps the comparison intact.
       */}
      <Card className="grid grid-cols-2 divide-y divide-line lg:grid-cols-4 lg:divide-x lg:divide-y-0">
        <Stat
          label="Collected"
          value={formatCurrency(summary.total_collected)}
          sub={`${summary.paid_count} paid`}
          emphasis={summary.total_collected > 0 ? "paid" : undefined}
        />
        <Stat
          label="Outstanding"
          value={formatCurrency(summary.total_outstanding)}
          sub={`${summary.pending_count} pending`}
        />
        <Stat
          label="Overdue"
          value={formatCurrency(summary.total_overdue)}
          sub={`${summary.overdue_count} past due`}
          emphasis={hasOverdue ? "overdue" : undefined}
        />
        <Stat
          label="Collection rate"
          value={`${summary.collection_rate}%`}
          sub="of invoiced value"
        />
      </Card>

      {hasOverdue && (
        <Alert tone="warning" title={`${summary.overdue_count} invoice(s) past due`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p>
              <Link href="/invoices" className="underline underline-offset-2">
                Review overdue invoices
              </Link>
              , or let the collections agent draft reminders automatically.
            </p>
            <Button variant="demo" size="sm" loading={agentRunning} onClick={runAgent}>
              <Sparkles aria-hidden className="h-3.5 w-3.5" />
              Run collections agent
            </Button>
          </div>
        </Alert>
      )}

      {agentResult && (
        <Alert tone={agentResult.reminders_sent.length > 0 ? "success" : "info"}>
          {agentResult.reminders_sent.length === 0 ? (
            <p>
              Reviewed {agentResult.invoices_reviewed} overdue invoice(s) — every one already has a
              reminder out at its current tier.
            </p>
          ) : (
            <div>
              <p className="font-medium">
                Sent {agentResult.reminders_sent.length} reminder(s) automatically:
              </p>
              <ul className="mt-2 space-y-1">
                {agentResult.reminders_sent.map((r) => (
                  <li key={r.invoice_id} className="tabular">
                    {r.invoice_number} — {TIER_LABEL[r.tier] ?? r.tier} ({r.days_overdue}d overdue)
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <CardTitle>Collection breakdown</CardTitle>
          <div className="mt-4">
            <CollectionChart data={summary.chart_data} />
          </div>
        </Card>

        <Card className="flex flex-col p-6">
          <CardTitle>Recent activity</CardTitle>
          {activity.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center py-10 text-center">
              <Inbox aria-hidden className="h-5 w-5 text-content-muted" />
              <p className="mt-3 text-sm text-content-muted">
                Activity appears here once you create an invoice.
              </p>
            </div>
          ) : (
            <ul className="mt-4 divide-y divide-line">
              {activity.slice(0, 8).map((event) => (
                <li key={event.id} className="py-2.5 first:pt-0 last:pb-0">
                  <p className="text-sm text-content-secondary">{event.message}</p>
                  <p className="tabular mt-0.5 text-xs text-content-muted">
                    {formatDateTime(event.created_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/*
       * This block shows the actual input format rather than repeating the
       * header's CTA as a third identical button.
       */}
      <Card className="border-accent/30 bg-accent/[0.07] p-6">
        <CardTitle>One sentence becomes an invoice</CardTitle>
        <p className="mt-1.5 text-sm text-content-secondary">
          Describe the work in plain English and SettleFlow extracts the customer, amount, and due
          date.
        </p>
        <p className="mt-4 rounded-lg border border-line bg-surface-sunken px-4 py-3 font-mono text-xs text-content-secondary">
          {DEMO_COMMAND}
        </p>
        <Link
          href="/invoices/new"
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent-text hover:underline"
        >
          Collect payment
          <ArrowRight aria-hidden className="h-4 w-4" />
        </Link>
      </Card>
    </div>
  );
}
