"use client";

import { useEffect, useState } from "react";
import { Card, CardTitle } from "@/components/ui";
import { api, type AuditSource, type InvoiceAuditEvent } from "@/lib/api";
import { cn, formatDateTime, truncateHash } from "@/lib/utils";

const SOURCE_STYLES: Record<AuditSource, { label: string; dot: string; chip: string }> = {
  user: {
    label: "User",
    dot: "bg-accent",
    chip: "bg-accent/15 text-accent",
  },
  system: {
    label: "System",
    dot: "bg-content-muted",
    chip: "bg-neutral-tint text-content-muted",
  },
  blockchain: {
    label: "Chain",
    dot: "bg-chain",
    chip: "bg-chain-tint text-chain",
  },
  ai: {
    label: "AI",
    dot: "bg-pending",
    chip: "bg-pending-tint text-pending",
  },
};

const EVENT_COPY: Record<string, { title: string; description: string }> = {
  invoice_parsed: {
    title: "Invoice parsed",
    description: "Human intent captured as invoice fields",
  },
  invoice_confirmed: {
    title: "Merchant confirmed",
    description: "Merchant reviewed and confirmed the details",
  },
  invoice_created: {
    title: "Invoice created",
    description: "Invoice persisted and registered",
  },
  payment_page_opened: {
    title: "Payment page opened",
    description: "Customer opened the payment link",
  },
  payment_submitted: {
    title: "Payment submitted",
    description: "A payment attempt was submitted",
  },
  payment_detected: {
    title: "Payment detected",
    description: "On-chain payment event validated",
  },
  invoice_marked_paid: {
    title: "Marked paid",
    description: "Invoice reconciled as paid on the dashboard",
  },
  reminder_generated: {
    title: "Reminder generated",
    description: "A collections reminder was drafted or sent",
  },
  ai_query: {
    title: "AI query",
    description: "An AI assistant queried this invoice",
  },
};

function sourceStyle(source: string) {
  return SOURCE_STYLES[(source as AuditSource)] ?? SOURCE_STYLES.system;
}

function eventCopy(eventType: string) {
  return (
    EVENT_COPY[eventType] ?? {
      title: eventType.replace(/_/g, " "),
      description: "",
    }
  );
}

function evidenceBadge(evidence: Record<string, unknown> | null) {
  if (!evidence) return null;
  const tx = evidence.tx_hash;
  if (typeof tx === "string" && tx.length > 0) {
    return `TX: ${truncateHash(tx)}`;
  }
  const preview = evidence.email_preview;
  if (typeof preview === "string" && preview.length > 0) {
    return "Email preview";
  }
  const snippet = evidence.prompt_snippet;
  if (typeof snippet === "string" && snippet.length > 0) {
    return "Prompt logged";
  }
  return null;
}

export function AuditTimeline({
  invoiceId,
  refreshKey,
}: {
  invoiceId: number;
  refreshKey?: string;
}) {
  const [events, setEvents] = useState<InvoiceAuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .invoiceAudit(invoiceId)
      .then((res) => {
        if (!cancelled) setEvents(res.events);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load audit trail");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [invoiceId, refreshKey]);

  return (
    <Card className="p-6">
      <CardTitle>Audit trail</CardTitle>
      <p className="mt-1 text-xs text-content-muted">
        Append-only record of intent, confirmation, payment, and reconciliation.
      </p>
      <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Audit sources">
        {(Object.keys(SOURCE_STYLES) as AuditSource[]).map((source) => {
          const style = SOURCE_STYLES[source];
          return (
            <li
              key={source}
              className={cn(
                "inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px] uppercase tracking-wide",
                style.chip
              )}
            >
              <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
              {style.label}
            </li>
          );
        })}
      </ul>

      {loading ? (
        <p className="mt-4 text-sm text-content-muted">Loading audit trail…</p>
      ) : error ? (
        <p className="mt-4 text-sm text-overdue">{error}</p>
      ) : events.length === 0 ? (
        <p className="mt-4 text-sm text-content-muted">
          No audit events have been recorded for this invoice yet.
        </p>
      ) : (
        <ol className="mt-4">
          {events.map((event, i) => {
            const style = sourceStyle(event.source);
            const copy = eventCopy(event.event_type);
            const badge = evidenceBadge(event.evidence);
            return (
              <li key={event.id} className="relative flex gap-3 pb-5 last:pb-0">
                {i < events.length - 1 && (
                  <span
                    aria-hidden
                    className="absolute left-[3px] top-3 h-full w-px bg-line"
                  />
                )}
                <span
                  aria-hidden
                  className={cn(
                    "relative mt-1.5 h-[7px] w-[7px] shrink-0 rounded-full",
                    style.dot
                  )}
                />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm text-content">{copy.title}</p>
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide",
                        style.chip
                      )}
                    >
                      {style.label}
                    </span>
                  </div>
                  {copy.description && (
                    <p className="mt-0.5 text-sm text-content-secondary">{copy.description}</p>
                  )}
                  {badge && (
                    <p
                      title={
                        typeof event.evidence?.tx_hash === "string"
                          ? event.evidence.tx_hash
                          : undefined
                      }
                      className="tabular mt-1 inline-flex rounded border border-line px-1.5 py-0.5 font-mono text-[11px] text-chain"
                    >
                      {badge}
                    </p>
                  )}
                  <p className="tabular mt-0.5 text-xs text-content-muted">
                    {formatDateTime(event.created_at)}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
