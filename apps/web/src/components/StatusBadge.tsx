import { cn } from "@/lib/utils";

/*
 * All seven InvoiceStatus values from the backend model, not just the three
 * the demo path exercises. Each carries a dot as well as a hue so status never
 * depends on color alone.
 */
const statuses: Record<string, { label: string; className: string; dot: string }> = {
  draft: { label: "Draft", className: "bg-neutral-tint text-neutral", dot: "bg-neutral" },
  pending: { label: "Pending", className: "bg-pending-tint text-pending", dot: "bg-pending" },
  partially_paid: {
    label: "Partially paid",
    className: "bg-paid-tint text-paid",
    dot: "bg-paid/50",
  },
  paid: { label: "Paid", className: "bg-paid-tint text-paid", dot: "bg-paid" },
  overdue: { label: "Overdue", className: "bg-overdue-tint text-overdue", dot: "bg-overdue" },
  disputed: {
    label: "Disputed",
    className: "bg-disputed-tint text-disputed",
    dot: "bg-disputed",
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-neutral-tint text-neutral",
    dot: "bg-neutral/50",
  },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const meta = statuses[status] ?? {
    // An unknown status is shown verbatim rather than silently relabelled "Draft".
    label: status.replace(/_/g, " "),
    className: "bg-neutral-tint text-neutral",
    dot: "bg-neutral",
  };

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        meta.className,
        className
      )}
    >
      <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
      {meta.label}
    </span>
  );
}
