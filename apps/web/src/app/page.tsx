"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Inbox, Sparkles, WifiOff } from "lucide-react";
import { CollectionChart } from "@/components/CollectionChart";
import { ChatPanel } from "@/components/ChatPanel";
import { StatusBadge } from "@/components/StatusBadge";
import { Alert, Button, Card, Metric, Skeleton } from "@/components/ui";
import {
  api,
  type ActivityEvent,
  type CollectionsAgentResult,
  type DashboardSummary,
  type Invoice,
} from "@/lib/api";
import { EASE_OUT, staggerContainer, staggerItem } from "@/lib/motion";
import {
  activityLabel,
  activityLane,
  cn,
  daysUntil,
  formatCurrency,
  formatDateTime,
} from "@/lib/utils";

const TIER_LABEL: Record<string, string> = {
  friendly: "Friendly nudge",
  firm: "Firm follow-up",
  final: "Final notice",
};

const DEMO_COMMAND = "Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.";

function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      <div>
        <Skeleton className="h-10 w-80 max-w-full" />
        <Skeleton className="mt-3 h-4 w-64" />
      </div>
      <Card className="grid grid-cols-2 divide-line lg:grid-cols-4 lg:divide-x">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="px-5 py-5">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="mt-3 h-8 w-28" />
            <Skeleton className="mt-2 h-3 w-24" />
          </div>
        ))}
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-[22rem] rounded" />
        <Skeleton className="h-[22rem] rounded" />
      </div>
    </div>
  );
}

export default function OverviewPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentResult, setAgentResult] = useState<CollectionsAgentResult | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([api.dashboard(), api.activity(), api.invoices()])
      .then(([s, a, inv]) => {
        setSummary(s);
        setActivity(a);
        setInvoices(inv);
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
  const overdueInvoices = invoices
    .filter((inv) => inv.status === "overdue")
    .sort((a, b) => daysUntil(a.due_date) - daysUntil(b.due_date));

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="space-y-10"
    >
      <motion.div variants={staggerItem} className="flex flex-wrap items-end justify-between gap-5">
        <div className="max-w-xl">
          <h1 className="text-3xl font-semibold tracking-tight text-content sm:text-4xl">
            Your collection desk, without the spreadsheet.
          </h1>
          <p className="mt-3 text-sm text-content-muted">
            AI parses. The chain verifies.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/invoices/new"
            className="inline-flex items-center gap-2 rounded bg-accent px-4 py-2 text-sm font-medium text-accent-on transition-colors duration-150 hover:bg-accent-hover"
          >
            Collect payment
          </Link>
          <Button variant="demo" size="sm" loading={agentRunning} onClick={runAgent}>
            <Sparkles aria-hidden className="h-3.5 w-3.5" />
            Run collections agent
          </Button>
        </div>
      </motion.div>

      <motion.div variants={staggerItem}>
      <Card className="grid grid-cols-2 divide-y divide-line lg:grid-cols-4 lg:divide-x lg:divide-y-0">
        <Metric
          label="Collected"
          value={formatCurrency(summary.total_collected)}
          sub={`${summary.paid_count} paid`}
          emphasis={summary.total_collected > 0 ? "paid" : undefined}
        />
        <Metric
          label="Outstanding"
          value={formatCurrency(summary.total_outstanding)}
          sub={`${summary.pending_count} pending`}
        />
        <Metric
          label="Overdue"
          value={formatCurrency(summary.total_overdue)}
          sub={`${summary.overdue_count} past due`}
          emphasis={hasOverdue ? "overdue" : undefined}
        />
        <Metric
          label="Collection rate"
          value={`${summary.collection_rate}%`}
          sub="of invoiced value"
        />
      </Card>
      </motion.div>

      {overdueInvoices.length > 0 && (
        <motion.section variants={staggerItem}>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-medium tracking-tight text-content">Needs attention</h2>
              <p className="mt-1 text-sm text-content-muted">
                {overdueInvoices.length} overdue invoice{overdueInvoices.length === 1 ? "" : "s"}{" "}
                still waiting on payment.
              </p>
            </div>
            <Button variant="demo" size="sm" loading={agentRunning} onClick={runAgent}>
              <Sparkles aria-hidden className="h-3.5 w-3.5" />
              Run agent
            </Button>
          </div>
          <Card className="mt-4 divide-y divide-line">
            {overdueInvoices.map((inv) => {
              const days = Math.abs(Math.min(daysUntil(inv.due_date), 0));
              return (
                <div
                  key={inv.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5"
                >
                  <div className="min-w-0">
                    <p className="font-mono text-sm text-content">{inv.invoice_number}</p>
                    <p className="truncate text-sm text-content-secondary">{inv.customer_name}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-4">
                    <p className="tabular font-mono text-sm text-content">
                      {formatCurrency(inv.amount, inv.currency)}
                    </p>
                    <p className="tabular text-xs text-overdue">
                      {days === 1 ? "1 day overdue" : `${days} days overdue`}
                    </p>
                    <p className="text-xs text-content-muted">
                      {inv.reminder_count} reminder{inv.reminder_count === 1 ? "" : "s"}
                    </p>
                    <StatusBadge status={inv.status} />
                    <Link
                      href={`/invoices/${inv.id}`}
                      className="text-sm font-medium text-accent-text transition-colors duration-150 hover:text-content"
                    >
                      Review invoice
                    </Link>
                  </div>
                </div>
              );
            })}
          </Card>
        </motion.section>
      )}

      <AnimatePresence>
      {agentResult && (
        <motion.div
          initial={{ opacity: 0, y: -8, height: 0 }}
          animate={{ opacity: 1, y: 0, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.35, ease: EASE_OUT }}
        >
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
                  <li key={r.invoice_id} className="tabular font-mono text-sm">
                    {r.invoice_number} — {TIER_LABEL[r.tier] ?? r.tier} ({r.days_overdue}d overdue)
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Alert>
        </motion.div>
      )}
      </AnimatePresence>

      <motion.div variants={staggerItem} className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <CollectionChart data={summary.chart_data} />
        </Card>

        <Card className="flex flex-col p-6">
          <h2 className="text-lg font-medium tracking-tight text-content">Recent activity</h2>
          {activity.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center py-10 text-center">
              <Inbox aria-hidden className="h-5 w-5 text-content-muted" />
              <p className="mt-3 text-sm text-content-muted">
                Activity appears here once you create an invoice.
              </p>
            </div>
          ) : (
            <motion.ul
              variants={staggerContainer}
              initial="hidden"
              animate="show"
              className="mt-4 divide-y divide-line"
            >
              {activity.slice(0, 8).map((event) => {
                const lane = activityLane(event.event_type);
                return (
                  <motion.li key={event.id} variants={staggerItem} className="py-2.5 first:pt-0 last:pb-0">
                    <div className="flex items-baseline gap-2">
                      <span
                        className={cn(
                          "shrink-0 text-[11px] font-medium uppercase tracking-wide",
                          lane === "chain" && "text-chain",
                          lane === "agent" && "text-pending",
                          lane === "merchant" && "text-content-muted"
                        )}
                      >
                        {lane}
                      </span>
                      <span className="text-[11px] text-content-muted">
                        {activityLabel(event.event_type)}
                      </span>
                    </div>
                    <p
                      className={cn(
                        "mt-0.5 text-sm",
                        lane === "chain" ? "font-mono text-xs text-chain" : "text-content-secondary"
                      )}
                    >
                      {event.message}
                    </p>
                    <p className="tabular mt-0.5 text-xs text-content-muted">
                      {formatDateTime(event.created_at)}
                    </p>
                  </motion.li>
                );
              })}
            </motion.ul>
          )}
        </Card>
      </motion.div>

      <motion.div variants={staggerItem}>
      <ChatPanel
        scope="overview"
        inputId="overview-chat"
        suggestions={[
          "What's my collection rate?",
          "Who is late?",
          "How does an invoice get marked paid?",
        ]}
      />
      </motion.div>

      <motion.div variants={staggerItem}>
      <Card className="p-6">
        <h2 className="text-lg font-medium tracking-tight text-content">
          One sentence becomes an invoice
        </h2>
        <p className="mt-1.5 text-sm text-content-secondary">
          Describe the work in plain English. SettleFlow extracts the customer, amount, and due
          date. No payment action is taken until you confirm.
        </p>
        <p className="mt-4 rounded border border-line bg-surface-sunken px-4 py-3 font-mono text-xs text-content-secondary">
          {DEMO_COMMAND}
        </p>
        <Link
          href="/invoices/new"
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent-text transition-colors duration-150 hover:text-content"
        >
          Collect payment
          <ArrowRight aria-hidden className="h-4 w-4" />
        </Link>
      </Card>
      </motion.div>
    </motion.div>
  );
}
