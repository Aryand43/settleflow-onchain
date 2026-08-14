export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

/*
 * Session token. Lives in localStorage rather than an httpOnly cookie because
 * the API is a separate origin and this is a prototype — good enough to keep
 * accounts apart, not good enough to be the only thing guarding real money.
 *
 * This replaces NEXT_PUBLIC_API_KEY, which shipped the admin key to every
 * browser that loaded the dashboard.
 */
const TOKEN_KEY = "settleflow.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export class UnauthorizedError extends Error {
  constructor(message = "Sign in to continue") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

export type User = {
  id: number;
  name: string;
  email: string;
  business_name: string | null;
  wallet_address: string;
  created_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type EmailStatus = {
  configured: boolean;
  from_address: string | null;
};

export type CustomerImportResult = {
  imported: number;
  skipped: number;
  customers: Customer[];
  errors: string[];
};

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

export type ChatScope = "payments" | "overview";

export type ChatTurn = {
  role: "user" | "assistant";
  content: string;
};

export type ChatStatus = {
  configured: boolean;
};

export type ChatReply = {
  reply: string;
  scope: ChatScope;
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
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401 && auth) {
    // The token is gone or expired. Drop it so the app stops retrying with a
    // credential the server has already rejected.
    clearToken();
    const err = await res.json().catch(() => ({ detail: "Session expired" }));
    throw new UnauthorizedError(err.detail || "Session expired");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

async function apiUpload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);

  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  // Deliberately no Content-Type — the browser sets the multipart boundary.

  const res = await fetch(`${API_URL}${path}`, { method: "POST", body, headers });
  if (res.status === 401) {
    clearToken();
    throw new UnauthorizedError();
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export const api = {
  health: () => apiFetch<{ status: string }>("/api/health", {}, false),

  signup: (data: {
    name: string;
    email: string;
    password: string;
    business_name?: string;
    wallet_address?: string;
  }) => apiFetch<AuthResponse>("/api/auth/signup", { method: "POST", body: JSON.stringify(data) }, false),
  login: (email: string, password: string) =>
    apiFetch<AuthResponse>(
      "/api/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false
    ),
  me: () => apiFetch<User>("/api/auth/me"),

  createCustomer: (data: {
    name: string;
    email: string;
    company?: string;
    wallet_address?: string;
  }) => apiFetch<Customer>("/api/customers", { method: "POST", body: JSON.stringify(data) }),
  deleteCustomer: (id: number) =>
    apiFetch<void>(`/api/customers/${id}`, { method: "DELETE" }),
  importCustomers: (file: File) =>
    apiUpload<CustomerImportResult>("/api/customers/import", file),

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
  emailStatus: () => apiFetch<EmailStatus>("/api/email/status"),
  sendInvoice: (id: number) =>
    apiFetch<{ message: string; delivered: boolean; path: string }>(
      `/api/invoices/${id}/send`,
      { method: "POST" }
    ),
  simulatePayment: (id: number) =>
    apiFetch<{ message: string; invoice: Invoice }>(`/api/invoices/${id}/simulate-payment`, {
      method: "POST",
    }),
  simulateTime: (id: number) =>
    apiFetch<{ message: string; invoice: Invoice }>(`/api/invoices/${id}/simulate-time`, {
      method: "POST",
    }),
  sendReminder: (id: number) =>
    apiFetch<{ message: string; delivered: boolean; invoice: Invoice }>(
      `/api/invoices/${id}/send-reminder`,
      { method: "POST" }
    ),
  paymentPage: (token: string) =>
    apiFetch<PaymentPage>(`/api/invoices/by-token/${token}/payment-page`, {}, false),
  payByToken: (token: string) =>
    apiFetch<{ message: string; payment_page: PaymentPage }>(
      `/api/invoices/by-token/${token}/pay`,
      { method: "POST" },
      false
    ),
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
  scanBlockchain: () =>
    apiFetch<{ processed: number; message: string }>("/api/blockchain/scan", { method: "POST" }),
  chatStatus: () => apiFetch<ChatStatus>("/api/chat/status"),
  chat: (data: { message: string; scope: ChatScope; history: ChatTurn[] }) =>
    apiFetch<ChatReply>("/api/chat", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
