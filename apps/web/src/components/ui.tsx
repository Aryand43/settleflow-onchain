"use client";

import { useEffect, useRef, useState } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Check, Copy, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/*
 * Shared primitives. Before this file, six pages each hand-rolled their own
 * button, card, and alert, which is why "muted text" had eleven definitions
 * and no control had a focus state.
 */

const buttonStyles = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-accent text-accent-on hover:bg-accent-hover",
        secondary: "bg-surface-raised text-content hover:bg-line-strong",
        quiet: "text-content-secondary hover:bg-surface-raised hover:text-content",
        /*
         * Demo controls simulate events the product would otherwise learn from
         * the chain. They get a dashed edge so they never read as an action
         * that moves real money — see PRODUCT.md, principle 1.
         */
        demo: "border border-dashed border-line-strong bg-transparent text-content-secondary hover:border-content-muted hover:text-content",
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
      className={cn(
        "rounded-xl border border-line bg-surface shadow-card",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-base font-medium text-content">{children}</h2>;
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-content">{title}</h1>
        {description && <p className="mt-1.5 text-sm text-content-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

const alertStyles = cva("rounded-lg border p-4 text-sm", {
  variants: {
    tone: {
      error: "border-overdue/40 bg-overdue-tint/60 text-overdue",
      success: "border-paid/40 bg-paid-tint/60 text-paid",
      warning: "border-pending/40 bg-pending-tint/60 text-pending",
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
  return <div className={cn("skeleton rounded-md", className)} />;
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
    <div className="flex flex-col items-center rounded-xl border border-dashed border-line-strong px-6 py-14 text-center">
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
      <label htmlFor={htmlFor} className="block text-sm font-medium text-content-secondary">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-content-muted">{hint}</p>}
    </div>
  );
}

/**
 * The demo script asks the merchant to "copy the payment URL", but the app only
 * ever rendered it as a link to select by hand.
 */
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
      // Clipboard blocked (insecure origin or denied permission) — leave the
      // label unchanged rather than claiming a copy that did not happen.
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg border border-line-strong px-2.5 py-1.5 text-xs font-medium text-content-secondary transition-colors duration-150 hover:border-content-muted hover:text-content",
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
  "w-full rounded-lg border border-line-strong bg-surface-sunken px-3 py-2 text-sm text-content placeholder:text-content-muted transition-colors duration-150 hover:border-content-muted";
