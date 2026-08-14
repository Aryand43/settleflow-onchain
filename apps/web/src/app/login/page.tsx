"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Alert, Button, inputStyles } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { user, signIn } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn(email.trim(), password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
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
          Sign in to your dashboard
        </h1>

        <form onSubmit={handleSubmit} className="mt-7 space-y-4">
          {error && <Alert tone="error">{error}</Alert>}

          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-content">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
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
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputStyles}
            />
          </div>

          <Button type="submit" size="lg" loading={submitting}>
            Sign in
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-content-muted">
          No account?{" "}
          <Link href="/signup" className="font-medium text-accent underline-offset-2 hover:underline">
            Create one
          </Link>
        </p>

        <div className="mt-8 rounded border border-dashed border-line-strong p-3.5 text-center text-xs text-content-muted">
          <p className="font-medium text-content-secondary">Demo account</p>
          <p className="mt-1 font-mono">demo@settleflow.app · settleflow</p>
          <p className="mt-1.5">Comes preloaded with three customers and three invoices.</p>
        </div>
      </div>
    </main>
  );
}
