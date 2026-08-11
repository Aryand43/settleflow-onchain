"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CollectionChart } from "@/components/CollectionChart";
import { api, type ActivityEvent, type DashboardSummary } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

export default function OverviewPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.dashboard(), api.activity()])
      .then(([s, a]) => {
        setSummary(s);
        setActivity(a);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-slate-400">Loading dashboard...</div>;
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">
        Failed to load dashboard. Is the API running? ({error})
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-white">Overview</h1>
        <p className="mt-1 text-slate-400">Track collections across your stablecoin invoices.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total collected" value={formatCurrency(summary.total_collected)} />
        <StatCard label="Outstanding" value={formatCurrency(summary.total_outstanding)} />
        <StatCard label="Overdue" value={formatCurrency(summary.total_overdue)} />
        <StatCard
          label="Collection rate"
          value={`${summary.collection_rate}%`}
          sub={`${summary.paid_count} paid · ${summary.pending_count} pending`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
          <h2 className="mb-4 text-lg font-medium text-white">Collection breakdown</h2>
          <CollectionChart data={summary.chart_data} />
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
          <h2 className="mb-4 text-lg font-medium text-white">Recent activity</h2>
          {activity.length === 0 ? (
            <p className="text-sm text-slate-500">No activity yet.</p>
          ) : (
            <ul className="space-y-3">
              {activity.slice(0, 8).map((event) => (
                <li key={event.id} className="border-b border-slate-800 pb-3 last:border-0">
                  <p className="text-sm text-slate-200">{event.message}</p>
                  <p className="text-xs text-slate-500">{formatDate(event.created_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-6">
        <h2 className="text-lg font-medium text-white">Ready to collect?</h2>
        <p className="mt-1 text-sm text-slate-300">
          Type a natural-language command to create an invoice in seconds.
        </p>
        <Link
          href="/invoices/new"
          className="mt-4 inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
        >
          Collect payment
        </Link>
      </div>
    </div>
  );
}
