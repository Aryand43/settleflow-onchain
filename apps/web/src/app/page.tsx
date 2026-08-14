"use client";

import Link from "next/link";
import { ArrowRight, Bot, Link2, ShieldCheck, Wallet } from "lucide-react";
import { useAuth } from "@/lib/auth";

const STEPS = [
  {
    icon: Wallet,
    title: "Describe the work",
    body: "“Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.” The invoice writes itself and registers on-chain.",
  },
  {
    icon: Link2,
    title: "Send one link",
    body: "Your client sees what's owed and pays in stablecoin. No account, no wallet-connect dance, no three-day wire.",
  },
  {
    icon: Bot,
    title: "Stop chasing",
    body: "Late invoices get followed up automatically — friendly, then firm, then final. Clients can ask for a few more days and get an answer immediately.",
  },
];

const BOUNDARIES = [
  "It can't move money — no send, no receive, no signing.",
  "It can't mark an invoice paid. Only a confirmed on-chain payment does that.",
  "It can't change what you're owed. It can shift a deadline by a few days, nothing more.",
];

export default function LandingPage() {
  const { user } = useAuth();

  return (
    <main className="min-h-screen bg-canvas text-content">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-5 py-5">
        <span className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="flex h-8 w-8 items-center justify-center rounded bg-accent text-xs font-bold text-accent-on"
          >
            SF
          </span>
          <span className="font-semibold tracking-tight">SettleFlow</span>
        </span>

        <nav className="flex items-center gap-2">
          {user ? (
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-1.5 rounded bg-accent px-4 py-2 text-sm font-medium text-accent-on transition-colors duration-150 hover:bg-accent-hover"
            >
              Open dashboard
              <ArrowRight aria-hidden className="h-4 w-4" />
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded px-3 py-2 text-sm font-medium text-content-secondary transition-colors duration-150 hover:text-content"
              >
                Sign in
              </Link>
              <Link
                href="/signup"
                className="rounded bg-accent px-4 py-2 text-sm font-medium text-accent-on transition-colors duration-150 hover:bg-accent-hover"
              >
                Get started
              </Link>
            </>
          )}
        </nav>
      </header>

      <section className="mx-auto max-w-3xl px-5 pb-16 pt-16 text-center sm:pt-24">
        <p className="text-sm font-medium text-accent">For freelancers billing across borders</p>
        <h1 className="mt-4 text-balance text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
          Get paid in stablecoins. Stop writing the follow-up email.
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-balance text-base leading-relaxed text-content-secondary">
          You invoice a client in Jakarta from Singapore. The money takes three days and two banks
          take a cut, and when it&rsquo;s late, chasing it is a job nobody wants. SettleFlow does
          both jobs.
        </p>

        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 rounded bg-accent px-5 py-2.5 text-sm font-medium text-accent-on transition-colors duration-150 hover:bg-accent-hover"
          >
            Create your account
            <ArrowRight aria-hidden className="h-4 w-4" />
          </Link>
          <Link
            href="/login"
            className="rounded border border-line-strong px-5 py-2.5 text-sm font-medium text-content-secondary transition-colors duration-150 hover:border-content-muted hover:text-content"
          >
            Try the demo account
          </Link>
        </div>

        <p className="mt-4 text-xs text-content-muted">
          Testnet only — no real funds move.
        </p>
      </section>

      <section className="mx-auto max-w-5xl px-5 pb-20">
        <div className="grid gap-4 sm:grid-cols-3">
          {STEPS.map((step) => (
            <div key={step.title} className="rounded border border-line bg-surface p-6">
              <step.icon aria-hidden className="h-5 w-5 text-accent" />
              <h2 className="mt-4 text-base font-medium">{step.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-content-secondary">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-line bg-surface">
        <div className="mx-auto max-w-3xl px-5 py-16">
          <span className="inline-flex items-center gap-2 text-sm font-medium text-accent">
            <ShieldCheck aria-hidden className="h-4 w-4" />
            The part that matters
          </span>
          <h2 className="mt-4 text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
            An agent handles your collections. It never touches your money.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-content-secondary">
            Plenty of tools will point a language model at your invoices. The question worth asking
            is what happens when it gets something wrong. Here, the answer is bounded by the code,
            not by a prompt:
          </p>

          <ul className="mt-6 space-y-3">
            {BOUNDARIES.map((line) => (
              <li key={line} className="flex gap-3 text-sm leading-relaxed text-content-secondary">
                <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />
                {line}
              </li>
            ))}
          </ul>

          <p className="mt-6 text-sm leading-relaxed text-content-secondary">
            An invoice becomes paid when the blockchain says so — when the payment is confirmed
            on-chain and the backend sees it. Not when the agent thinks so, and not when you click
            something.
          </p>
        </div>
      </section>

      <footer className="mx-auto max-w-5xl px-5 py-10 text-center">
        <p className="text-sm text-content-muted">
          Built for a hackathon. Testnet funds only.{" "}
          <Link href="/signup" className="text-accent underline-offset-2 hover:underline">
            Start collecting
          </Link>
        </p>
      </footer>
    </main>
  );
}
