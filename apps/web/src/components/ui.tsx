"use client";

import { useEffect, useRef, useState } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Check, Copy, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const buttonStyles = cva(
  "inline-flex items-center justify-center gap-2 rounded text-sm font-medium transition-[background-color,transform,box-shadow] duration-150 ease-out active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100",
  {
    variants: {
      variant: {
        primary: "bg-accent text-accent-on hover:bg-accent-hover",
        secondary: "border border-line-strong bg-surface-raised text-content hover:border-content-muted",
        quiet: "text-content-secondary hover:bg-surface-raised hover:text-content",
        demo: "border border-dashed border-overdue/50 bg-overdue-tint/40 text-overdue hover:border-overdue",
      },
      size: {
        sm: "px-3 py-1.5",
        md: "px-4 py-2",
        lg: "w-full px-4 py-3",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonStyles> & { loading?: boolean };

export function Button({
  className,
  variant,
  size,
  loading,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(buttonStyles({ variant, size }), className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 aria-hidden className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Card({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded border border-line bg-surface shadow-card", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export const Panel = Card;

export function CardTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-lg font-medium tracking-tight text-content">{children}</h2>;
}

export function SectionHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
}) {
  return (
    <div>
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h2 className={cn("text-lg font-medium tracking-tight text-content", eyebrow && "mt-2")}>
        {title}
      </h2>
      {description && <p className="mt-1 text-sm text-content-muted">{description}</p>}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  action,
  eyebrow,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className={cn("text-3xl font-semibold tracking-tight text-content sm:text-4xl", eyebrow && "mt-2")}>
          {title}
        </h1>
        {description && <p className="mt-2 max-w-xl text-sm text-content-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function Metric({
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
    <div className="px-5 py-5">
      <p className="eyebrow">{label}</p>
      <p
        className={cn(
          "tabular mt-2 font-mono text-3xl font-medium tracking-tight",
          emphasis === "overdue" && "text-overdue",
          emphasis === "paid" && "text-paid",
          !emphasis && "text-content"
        )}
      >
        {value}
      </p>
      {sub && <p className="mt-1.5 text-xs text-content-muted">{sub}</p>}
    </div>
  );
}

export function DemoNotice({
  title = "Demo controls",
  children,
}: {
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded border border-dashed border-overdue/40 bg-overdue-tint/30 p-5">
      <p className="eyebrow text-overdue">{title}</p>
      <p className="mt-2 text-xs text-content-muted">
        These controls simulate the demo environment. They do not move real funds. Status
        flips to paid only after an InvoicePaid event is observed.
      </p>
      <div className="mt-4">{children}</div>
    </div>
  );
}

const alertStyles = cva("rounded border p-4 text-sm", {
  variants: {
    tone: {
      error: "border-disputed/40 bg-disputed-tint text-disputed",
      success: "border-paid/40 bg-paid-tint text-paid",
      warning: "border-overdue/40 bg-overdue-tint text-overdue",
      info: "border-line-strong bg-surface-raised text-content-secondary",
    },
  },
  defaultVariants: { tone: "info" },
});

export function Alert({
  tone,
  title,
  children,
  className,
}: VariantProps<typeof alertStyles> & {
  title?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(alertStyles({ tone }), className)}
    >
      {title && <p className="font-medium">{title}</p>}
      {children && <div className={cn(title && "mt-1 opacity-90")}>{children}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded", className)} />;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded border border-dashed border-line-strong px-6 py-14 text-center">
      <Icon aria-hidden className="h-6 w-6 text-content-muted" />
      <p className="mt-4 font-medium text-content">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-content-muted">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Field({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string;
  hint?: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="eyebrow block">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-content-muted">{hint}</p>}
    </div>
  );
}

export function CopyButton({
  value,
  label = "Copy",
  className,
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      timer.current = setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked */
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className={cn(
        "inline-flex items-center gap-1.5 rounded border border-line-strong px-2.5 py-1.5 text-xs font-medium text-content-secondary transition-colors duration-150 hover:border-content-muted hover:text-content",
        className
      )}
    >
      {copied ? (
        <Check aria-hidden className="h-3.5 w-3.5 text-paid" />
      ) : (
        <Copy aria-hidden className="h-3.5 w-3.5" />
      )}
      {copied ? "Copied" : label}
      <span aria-live="polite" className="sr-only">
        {copied ? "Copied to clipboard" : ""}
      </span>
    </button>
  );
}

export const inputStyles =
  "w-full rounded border border-line-strong bg-surface-sunken px-3 py-2 text-sm text-content placeholder:text-content-muted transition-colors duration-150 hover:border-content-muted";
