"use client";

import { useState } from "react";
import { PieChart } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

const fills: Record<string, string> = {
  Collected: "var(--chart-collected)",
  Outstanding: "var(--chart-outstanding)",
  Overdue: "var(--chart-overdue)",
};

type Datum = { name: string; value: number };

export function CollectionChart({ data }: { data: Datum[] }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const total = data.reduce((sum, d) => sum + d.value, 0);

  if (total <= 0) {
    return (
      <figure className="m-0">
        <div className="mb-5">
          <h2 className="text-lg font-medium tracking-tight text-content">
            Where money is in the pipeline
          </h2>
          <p className="mt-1 text-sm text-content-muted">
            Current invoice status across the workspace
          </p>
        </div>
        <div className="flex h-40 flex-col items-center justify-center border border-dashed border-line-strong text-center">
          <PieChart aria-hidden className="h-5 w-5 text-content-muted" />
          <p className="mt-3 text-sm text-content-muted">
            No invoiced value yet. The pipeline fills in as you create invoices.
          </p>
        </div>
      </figure>
    );
  }

  const segments = data.filter((d) => d.value > 0);

  return (
    <figure className="m-0">
      <div className="mb-5">
        <h2 className="text-lg font-medium tracking-tight text-content">
          Where money is in the pipeline
        </h2>
        <p className="mt-1 text-sm text-content-muted">
          Current invoice status across the workspace
        </p>
      </div>
      <div
        className="flex h-3 w-full gap-px overflow-hidden"
        role="img"
        aria-label={segments
          .map(
            (d) =>
              `${d.name} ${formatCurrency(d.value)}, ${Math.round((d.value / total) * 100)} percent`
          )
          .join("; ")}
      >
        {segments.map((d) => (
          <div
            key={d.name}
            onMouseEnter={() => setHovered(d.name)}
            onMouseLeave={() => setHovered(null)}
            style={{
              width: `${(d.value / total) * 100}%`,
              backgroundColor: fills[d.name] ?? "var(--neutral)",
              opacity: hovered && hovered !== d.name ? 0.4 : 1,
            }}
            className="h-full transition-opacity duration-150 ease-out"
          />
        ))}
      </div>
      <figcaption className="mt-5">
        <dl className="divide-y divide-line">
          {data.map((d) => {
            const share = total > 0 ? (d.value / total) * 100 : 0;
            return (
              <div
                key={d.name}
                onMouseEnter={() => setHovered(d.name)}
                onMouseLeave={() => setHovered(null)}
                className="flex items-center justify-between gap-4 py-2.5 first:pt-0 last:pb-0"
              >
                <dt className="flex min-w-0 items-center gap-2.5">
                  <span
                    aria-hidden
                    style={{ backgroundColor: fills[d.name] ?? "var(--neutral)" }}
                    className="h-2 w-2 shrink-0"
                  />
                  <span className="truncate text-sm text-content-secondary">{d.name}</span>
                </dt>
                <dd className="flex shrink-0 items-baseline gap-3">
                  <span className="tabular font-mono text-sm text-content">
                    {formatCurrency(d.value)}
                  </span>
                  <span className="tabular w-11 text-right text-xs text-content-muted">
                    {share.toFixed(share < 10 && share > 0 ? 1 : 0)}%
                  </span>
                </dd>
              </div>
            );
          })}
        </dl>
      </figcaption>
    </figure>
  );
}
