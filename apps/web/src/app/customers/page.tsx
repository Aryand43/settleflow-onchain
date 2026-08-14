"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Trash2, Upload, UserPlus, Users } from "lucide-react";
import {
  Alert,
  Button,
  Card,
  CardTitle,
  EmptyState,
  PageHeader,
  Skeleton,
  inputStyles,
} from "@/components/ui";
import { api, type Customer, type CustomerImportResult } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

const BLANK = { name: "", email: "", company: "", wallet_address: "" };

const SAMPLE_CSV = `name,email,company,wallet
Daniel Tan,daniel@example.com,Tan Design,0x70997970C51812dc3A010C7d01b50e0d17dc79C8
Sarah Lim,sarah@example.com,Lim Studio,
`;

export default function CustomersPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<CustomerImportResult | null>(null);
  const [importing, setImporting] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .customers()
      .then(setCustomers)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Could not load customers"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setSaving(true);
    try {
      const created = await api.createCustomer({
        name: form.name.trim(),
        email: form.email.trim(),
        company: form.company.trim() || undefined,
        wallet_address: form.wallet_address.trim() || undefined,
      });
      setForm(BLANK);
      setNotice(`${created.name} added to your directory.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add that customer");
    } finally {
      setSaving(false);
    }
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);
    setNotice(null);
    setImportResult(null);
    setImporting(true);
    try {
      const result = await api.importCustomers(file);
      setImportResult(result);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read that file");
    } finally {
      setImporting(false);
      // Clearing lets you re-upload the same file after fixing it.
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function handleDelete(customer: Customer) {
    setError(null);
    setNotice(null);
    try {
      await api.deleteCustomer(customer.id);
      setNotice(`${customer.name} removed.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove that customer");
    }
  }

  if (authLoading || !user) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div className="rise space-y-6">
      <PageHeader
        title="Customers"
        description="Who you can invoice. An invoice command only matches names that are in here."
      />

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      {importResult && (
        <Alert tone={importResult.errors.length > 0 ? "warning" : "success"}>
          <p className="font-medium">
            Imported {importResult.imported} customer(s)
            {importResult.skipped > 0 && `, skipped ${importResult.skipped} already-known or duplicate`}
            .
          </p>
          {importResult.errors.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs">
              {importResult.errors.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          )}
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Card className="p-6">
          <CardTitle>Directory</CardTitle>

          {loading ? (
            <div className="mt-4 space-y-2">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : customers.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                icon={Users}
                title="No customers yet"
                description="Add your first client on the right, or upload a CSV export from your existing invoicing tool."
              />
            </div>
          ) : (
            <ul className="mt-4 divide-y divide-line">
              {customers.map((customer) => (
                <li key={customer.id} className="flex items-center gap-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-content">
                      {customer.name}
                      {customer.company && (
                        <span className="font-normal text-content-muted"> · {customer.company}</span>
                      )}
                    </p>
                    <p className="truncate text-xs text-content-muted">{customer.email}</p>
                  </div>
                  {customer.wallet_address && (
                    <span className="hidden font-mono text-xs text-content-muted sm:block">
                      {customer.wallet_address.slice(0, 6)}…{customer.wallet_address.slice(-4)}
                    </span>
                  )}
                  <button
                    onClick={() => handleDelete(customer)}
                    title={`Remove ${customer.name}`}
                    className="rounded p-2 text-content-muted transition-colors duration-150 hover:bg-surface-raised hover:text-overdue"
                  >
                    <Trash2 aria-hidden className="h-4 w-4" />
                    <span className="sr-only">Remove {customer.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {customers.length > 0 && (
            <p className="mt-4 text-xs text-content-muted">
              {customers.length} customer{customers.length === 1 ? "" : "s"} ·{" "}
              <Link href="/invoices/new" className="text-accent underline-offset-2 hover:underline">
                Create an invoice
              </Link>
            </p>
          )}
        </Card>

        <div className="space-y-6">
          <Card className="p-6">
            <CardTitle>
              <span className="inline-flex items-center gap-2">
                <UserPlus aria-hidden className="h-4 w-4 text-content-muted" />
                Add a customer
              </span>
            </CardTitle>

            <form onSubmit={handleAdd} className="mt-4 space-y-3">
              <div>
                <label htmlFor="c-name" className="mb-1.5 block text-sm font-medium text-content">
                  Name
                </label>
                <input
                  id="c-name"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className={inputStyles}
                />
              </div>

              <div>
                <label htmlFor="c-email" className="mb-1.5 block text-sm font-medium text-content">
                  Email
                </label>
                <input
                  id="c-email"
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className={inputStyles}
                />
                <p className="mt-1.5 text-xs text-content-muted">
                  Where invoices and reminders are sent.
                </p>
              </div>

              <div>
                <label htmlFor="c-company" className="mb-1.5 block text-sm font-medium text-content">
                  Company <span className="font-normal text-content-muted">(optional)</span>
                </label>
                <input
                  id="c-company"
                  value={form.company}
                  onChange={(e) => setForm({ ...form, company: e.target.value })}
                  className={inputStyles}
                />
              </div>

              <div>
                <label htmlFor="c-wallet" className="mb-1.5 block text-sm font-medium text-content">
                  Wallet <span className="font-normal text-content-muted">(optional)</span>
                </label>
                <input
                  id="c-wallet"
                  placeholder="0x…"
                  value={form.wallet_address}
                  onChange={(e) => setForm({ ...form, wallet_address: e.target.value })}
                  className={`${inputStyles} font-mono text-xs`}
                />
              </div>

              <Button type="submit" size="lg" loading={saving}>
                Add customer
              </Button>
            </form>
          </Card>

          <Card className="p-6">
            <CardTitle>
              <span className="inline-flex items-center gap-2">
                <Upload aria-hidden className="h-4 w-4 text-content-muted" />
                Import a CSV
              </span>
            </CardTitle>
            <p className="mt-1.5 text-xs text-content-muted">
              Needs a name column and an email column; company and wallet are picked up if present.
              Rows that fail are reported individually — the rest still import.
            </p>

            <input
              ref={fileInput}
              type="file"
              accept=".csv,text/csv"
              onChange={handleFile}
              className="sr-only"
              id="csv-upload"
            />
            <Button
              type="button"
              variant="secondary"
              size="lg"
              className="mt-4"
              loading={importing}
              onClick={() => fileInput.current?.click()}
            >
              Choose CSV file
            </Button>

            <details className="mt-4">
              <summary className="cursor-pointer text-xs text-content-muted hover:text-content">
                What should the file look like?
              </summary>
              <pre className="mt-2 overflow-x-auto rounded bg-surface-sunken p-3 font-mono text-[11px] leading-relaxed text-content-secondary">
                {SAMPLE_CSV}
              </pre>
            </details>
          </Card>
        </div>
      </div>
    </div>
  );
}
