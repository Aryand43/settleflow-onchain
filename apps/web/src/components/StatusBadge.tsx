import { cn } from "@/lib/utils";

const statuses: Record<
  string,
  { label: string; className: string; mark: string; description: string }
> = {
  draft: {
    label: "Draft",
    className: "bg-neutral-tint text-neutral",
    mark: "○",
    description: "Not yet ready for collection",
  },
  pending: {
    label: "Pending",
    className: "bg-pending-tint text-pending",
    mark: "◐",
    description: "Awaiting payment",
  },
  partially_paid: {
    label: "Partially paid",
    className: "bg-overdue-tint text-overdue",
    mark: "◑",
    description: "Payment received but balance remains",
  },
  paid: {
    label: "Paid",
    className: "bg-paid-tint text-paid",
    mark: "●",
    description: "Payment confirmed on-chain",
  },
  overdue: {
    label: "Overdue",
    className: "bg-overdue-tint text-overdue",
    mark: "▲",
    description: "Due date passed",
  },
  disputed: {
    label: "Disputed",
    className: "bg-disputed-tint text-disputed",
    mark: "■",
    description: "Requires merchant attention",
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-neutral-tint text-neutral",
    mark: "✕",
    description: "No longer collectible",
  },
};

export function StatusBadge({
  status,
  className,
  size = "compact",
}: {
  status: string;
  className?: string;
  size?: "compact" | "large";
}) {
  const meta = statuses[status] ?? {
    label: status.replace(/_/g, " "),
    className: "bg-neutral-tint text-neutral",
    mark: "○",
    description: status,
  };

  return (
    <span
      role="status"
      aria-label={status}
      title={meta.description}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 font-medium",
        size === "large" ? "rounded px-3 py-1.5 text-sm" : "rounded px-2 py-1 text-xs",
        meta.className,
        className
      )}
    >
      <span aria-hidden className="font-mono text-[10px] leading-none">
        {meta.mark}
      </span>
      {meta.label}
    </span>
  );
}
