"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Alert, Button, inputStyles } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export default function SignupPage() {
  const { user, signUp } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({
    name: "",
    business_name: "",
    email: "",
    password: "",
    wallet_address: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  function update(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signUp({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        business_name: form.business_name.trim() || undefined,
        wallet_address: form.wallet_address.trim() || undefined,
      });
      router.push("/customers");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create your account");
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-canvas px-4 py-12">
      <div className="w-full max-w-sm">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2.5">
          <span
            aria-hidden
            className="flex h-9 w-9 items-center justify-center rounded bg-accent text-sm font-bold text-accent-on"
          >
            SF
          </span>
          <span className="text-lg font-semibold tracking-tight text-content">SettleFlow</span>
        </Link>

        <h1 className="text-center text-xl font-semibold tracking-tight text-content">
          Start collecting in stablecoins
        </h1>
        <p className="mt-1.5 text-center text-sm text-content-muted">
          Free while we&rsquo;re in testnet. No card, no wallet connection required.
        </p>

        <form onSubmit={handleSubmit} className="mt-7 space-y-4">
          {error && <Alert tone="error">{error}</Alert>}

          <div>
            <label htmlFor="name" className="mb-1.5 block text-sm font-medium text-content">
              Your name
            </label>
            <input
              id="name"
              required
              autoComplete="name"
              value={form.name}
              onChange={update("name")}
              className={inputStyles}
            />
          </div>

          <div>
            <label htmlFor="business" className="mb-1.5 block text-sm font-medium text-content">
              Business name{" "}
              <span className="font-normal text-content-muted">(optional)</span>
            </label>
            <input
              id="business"
              autoComplete="organization"
              placeholder="What clients see on the invoice"
              value={form.business_name}
              onChange={update("business_name")}
              className={inputStyles}
            />
          </div>

          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-content">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={update("email")}
              className={inputStyles}
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-content">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={form.password}
              onChange={update("password")}
              className={inputStyles}
            />
            <p className="mt-1.5 text-xs text-content-muted">At least 8 characters.</p>
          </div>

          <div>
            <label htmlFor="wallet" className="mb-1.5 block text-sm font-medium text-content">
              Payout wallet <span className="font-normal text-content-muted">(optional)</span>
            </label>
            <input
              id="wallet"
              placeholder="0x…"
              value={form.wallet_address}
              onChange={update("wallet_address")}
              className={`${inputStyles} font-mono text-xs`}
            />
            <p className="mt-1.5 text-xs text-content-muted">
              Where your invoices get paid. Leave blank to use the testnet demo wallet.
            </p>
          </div>

          <Button type="submit" size="lg" loading={submitting}>
            Create account
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-content-muted">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-accent underline-offset-2 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
