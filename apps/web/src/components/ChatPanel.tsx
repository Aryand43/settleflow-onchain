"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { Alert, Button, Card, inputStyles } from "@/components/ui";
import { api, type ChatScope, type ChatTurn } from "@/lib/api";
import { cn } from "@/lib/utils";

type ChatPanelProps = {
  scope: ChatScope;
  suggestions: string[];
  inputId: string;
  title?: string;
  description?: string;
};

export function ChatPanel({
  scope,
  suggestions,
  inputId,
  title = "SettleFlow assistant",
  description = "Read-only workspace answers",
}: ChatPanelProps) {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .chatStatus()
      .then((s) => setConfigured(s.configured))
      .catch(() => setConfigured(false));
  }, []);

  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || sending) return;

    const history = messages;
    const next: ChatTurn[] = [...messages, { role: "user", content: message }];
    setMessages(next);
    setDraft("");
    setSending(true);
    setError(null);

    try {
      const result = await api.chat({ message, scope, history });
      setMessages([...next, { role: "assistant", content: result.reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't get a reply.");
      setMessages(history);
      setDraft(message);
    } finally {
      setSending(false);
    }
  }

  return (
    <Card className="flex flex-col p-4">
      <div>
        <h2 className="text-sm font-medium tracking-tight text-content">{title}</h2>
        <p className="mt-0.5 text-xs text-content-muted">{description}</p>
      </div>

      {configured === null && (
        <p className="mt-3 text-xs text-content-muted">Checking whether chat is configured…</p>
      )}

      {configured === false && (
        <Alert tone="info" className="mt-3" title="Add an API key to enable this">
          Paste an OpenAI-compatible key into <code className="font-mono">LLM_API_KEY</code> in{" "}
          <code className="font-mono">apps/api/.env</code>, then restart the API.
        </Alert>
      )}

      {configured && (
        <>
          {messages.length > 0 && (
            <div
              ref={scroller}
              className="mt-3 max-h-48 space-y-2 overflow-y-auto pr-1"
            >
              {messages.map((m, i) => (
                <div
                  key={`${m.role}-${i}`}
                  className={cn(
                    "max-w-[85%] rounded px-3 py-2 text-sm",
                    m.role === "user"
                      ? "ml-auto bg-accent/10 text-content"
                      : "bg-surface-sunken text-content-secondary"
                  )}
                >
                  <p className="whitespace-pre-wrap">{m.content}</p>
                </div>
              ))}
              {sending && (
                <div
                  aria-live="polite"
                  className="flex items-center gap-2 text-xs text-content-muted"
                >
                  <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />
                  Reading your invoices…
                </div>
              )}
            </div>
          )}

          {messages.length === 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {suggestions.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => send(prompt)}
                  disabled={sending}
                  className="rounded border border-line-strong bg-transparent px-2.5 py-1 text-left text-xs text-content-secondary transition-colors duration-150 hover:border-content-muted hover:text-content disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}

          {error && (
            <Alert tone="error" className="mt-3">
              {error}
            </Alert>
          )}

          <form
            className="mt-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
          >
            <label htmlFor={inputId} className="sr-only">
              {title}
            </label>
            <input
              id={inputId}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask in plain English"
              disabled={sending}
              className={inputStyles}
            />
            <Button type="submit" size="md" loading={sending} disabled={!draft.trim()}>
              Ask
            </Button>
          </form>

          <p className="mt-2 text-xs text-content-muted">
            Answers from live data only. This cannot mark an invoice paid or move funds.
          </p>
        </>
      )}
    </Card>
  );
}
