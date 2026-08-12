export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-key";
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export type Customer = {
  id: number;
  name: string;
  email: string;
  wallet_address: string | null;
  company: string | null;
  created_at: string;
};

export type Invoice = {
  id: number;
  invoice_number: string;
  customer_id: number;
  customer_name: string | null;
  merchant_wallet: string;
  amount: number;
  currency: string;
  amount_wei_or_base_units: number;
  description: string;
  due_date: string;
  status: string;
  payment_url: string | null;
  payment_token: string;
  blockchain_tx_hash: string | null;
  on_chain_invoice_id: string | null;
  created_at: string;
  paid_at: string | null;
  reminder_count: number;
};

export type ParsedCommand = {
  customer_name: string;
  amount: number;
  currency: string;
  description: string;
  due_date: string;
  confidence: number;
  missing_fields: string[];
};

export type DashboardSummary = {
  total_collected: number;
  total_outstanding: number;
  total_overdue: number;
  paid_count: number;
  pending_count: number;
  overdue_count: number;
  collection_rate: number;
  chart_data: { name: string; value: number }[];
};

export type ActivityEvent = {
  id: number;
  invoice_id: number | null;
  event_type: string;
  message: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

export type NegotiationMessage = {
  id: number;
  invoice_id: number;
  sender: "customer" | "agent";
  message: string;
  created_at: string;
};

export type NegotiationReply = {
  intent: "extension" | "installment" | "generic";
  auto_granted: boolean;
  reply: string;
};

export type CollectionsAgentResult = {
  invoices_reviewed: number;
  reminders_sent: {
    invoice_id: number;
    invoice_number: string;
    tier: "friendly" | "firm" | "final";
    days_overdue: number;
  }[];
};

export type PaymentPage = {
  merchant_name: string;
  invoice_number: string;
  description: string;
  amount: number;
  currency: string;
  due_date: string;
  status: string;
  customer_name: string;
  payment_url: string;
  payment_token: string;
  on_chain_invoice_id: string | null;
  demo_mode: boolean;
  chain_configured: boolean;
};

async function apiFetch<T>(path: string, options: RequestInit = {}, auth = true): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (auth) headers["X-API-Key"] = API_KEY;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  health: () => apiFetch<{ status: string }>("/api/health", {}, false),
  dashboard: () => apiFetch<DashboardSummary>("/api/dashboard/summary"),
  activity: () => apiFetch<ActivityEvent[]>("/api/activity"),
  customers: () => apiFetch<Customer[]>("/api/customers"),
  invoices: () => apiFetch<Invoice[]>("/api/invoices"),
  invoice: (id: number) => apiFetch<Invoice>(`/api/invoices/${id}`),
  invoiceActivity: (id: number) => apiFetch<ActivityEvent[]>(`/api/invoices/${id}/activity`),
  parseCommand: (command: string) =>
    apiFetch<ParsedCommand>("/api/invoices/parse-command", {
      method: "POST",
      body: JSON.stringify({ command }),
    }),
  createInvoice: (data: {
    customer_id: number;
    amount: number;
    currency: string;
    description: string;
    due_date: string;
  }) =>
    apiFetch<Invoice>("/api/invoices", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  sendInvoice: (id: number) =>
    apiFetch<{ message: string; path: string }>(`/api/invoices/${id}/send`, { method: "POST" }),
  simulatePayment: (id: number) =>
    apiFetch<{ message: string; invoice: Invoice }>(`/api/invoices/${id}/simulate-payment`, {
      method: "POST",
    }),
  simulateTime: (id: number) =>
    apiFetch<{ message: string; invoice: Invoice }>(`/api/invoices/${id}/simulate-time`, {
      method: "POST",
    }),
  sendReminder: (id: number) =>
    apiFetch<{ message: string; invoice: Invoice }>(`/api/invoices/${id}/send-reminder`, {
      method: "POST",
    }),
  paymentPage: (token: string) =>
    apiFetch<PaymentPage>(`/api/invoices/by-token/${token}/payment-page`, {}, false),
  runCollectionsAgent: () =>
    apiFetch<CollectionsAgentResult>("/api/agent/run-collections", { method: "POST" }),
  paymentPageMessages: (token: string) =>
    apiFetch<NegotiationMessage[]>(`/api/invoices/by-token/${token}/messages`, {}, false),
  sendPaymentPageMessage: (token: string, message: string) =>
    apiFetch<NegotiationReply>(
      `/api/invoices/by-token/${token}/messages`,
      { method: "POST", body: JSON.stringify({ message }) },
      false
    ),
  invoiceMessages: (id: number) =>
    apiFetch<NegotiationMessage[]>(`/api/invoices/${id}/messages`),
};
