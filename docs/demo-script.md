# SettleFlow — 90-second demo script

## Setup (before judges arrive)

```bash
cd apps/api && source .venv/bin/activate && python scripts/seed.py
# Terminal 1: uvicorn app.main:app --reload --port 8000
# Terminal 2: cd apps/web && npm run dev
```

Open http://localhost:3000

---

## Script (~90 seconds)

**0:00 — Dashboard**
"This is SettleFlow — automated stablecoin invoice collection for Singapore freelancers. The overview shows what's collected, outstanding, and overdue."

**0:15 — Create invoice**
Click **Collect payment**. Paste:
`Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.`

Click **Parse command**. "The AI extracts customer, amount, currency, description, and due date — no manual form filling."

**0:35 — Customer match + create**
"Daniel Tan is matched from our customer directory." Click **Create invoice**. "Invoice INV-0004 is created, email preview saved, payment link generated."

**0:50 — Payment page**
Open the payment link. "Customers see a clean payment page with QR code. This is testnet-only."

**1:00 — Simulate payment**
Back on invoice detail, click **Simulate payment**. "Blockchain payment detected — status updates to Paid with a transaction hash."

**1:10 — Overdue demo**
Pick a pending invoice. Click **Simulate time**. "Due date moves to the past — invoice becomes overdue, reminder fires."

**1:20 — Reminder**
Click **Send reminder**. "Reminder HTML saved to email_previews — ready for SMTP in production."

**Wrap:** "End-to-end: natural language → invoice → payment → dashboard. All on testnet, demo-ready without external API keys."
