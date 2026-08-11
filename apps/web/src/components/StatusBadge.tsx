import { cn } from "@/lib/utils";

const statusStyles: Record<string, string> = {
  draft: "bg-slate-500/20 text-slate-300",
  pending: "bg-amber-500/20 text-amber-300",
  partially_paid: "bg-blue-500/20 text-blue-300",
  paid: "bg-emerald-500/20 text-emerald-300",
  overdue: "bg-red-500/20 text-red-300",
  disputed: "bg-purple-500/20 text-purple-300",
  cancelled: "bg-slate-600/20 text-slate-400",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
        statusStyles[status] || statusStyles.draft
      )}
    >
      {status.replace("_", " ")}
    </span>
  );
}
