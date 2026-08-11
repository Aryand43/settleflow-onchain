# SettleFlow

**Automated invoice collection for the global stablecoin economy.**

SettleFlow is a hackathon prototype that helps Singapore-based freelancers collect cross-border invoice payments using stablecoins. Type a natural-language command, create an invoice, share a payment link, and track status on a merchant dashboard.

> **Testnet demo only.** No real funds. `DEMO_MODE=true` by default.

---

## Quick start (5 minutes)

### Prerequisites

- Node.js 18+
- Python 3.9+

### Setup

```bash
git clone <repo-url> settleflow-onchain
cd settleflow-onchain

# Backend
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env.example .env   # or use the included apps/api/.env

# Frontend
cd ../web
npm install
cp ../../.env.example .env.local  # or use included .env.local
```

### Run

Terminal 1 — API:

```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2 — Web:

```bash
cd apps/web
npm run dev
```

Terminal 3 — Seed demo data:

```bash
cd apps/api
source .venv/bin/activate
python scripts/seed.py
```

Open [http://localhost:3000](http://localhost:3000).

Or from repo root: `make seed` then `make dev`.

---

## 90-second demo script

1. Open the dashboard — see collected/outstanding/overdue stats and seed invoices.
2. Click **Collect payment**.
3. Enter: `Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.`
4. Click **Parse command** — fields extract automatically (regex, no API key needed).
5. Confirm Daniel Tan matched from customer directory.
6. Click **Create invoice** — generates INV-0004 (or next sequential), email preview saved.
7. Open invoice detail — copy payment URL or scan QR code.
8. Open `/pay/{token}` — customer-facing payment page with amount and due date.
9. Click **Simulate payment** on invoice detail (DEMO_MODE).
10. Dashboard refreshes — status **Paid**, transaction hash shown.
11. Create or pick a pending invoice — click **Simulate time**.
12. Status becomes **Overdue**; reminder preview generated automatically.
13. Click **Send reminder** — HTML saved to `apps/api/email_previews/`.
14. Show activity timeline and collection chart updating.

---

## Architecture

```
Merchant Dashboard (Next.js)
        │
        ▼
   FastAPI Backend ── SQLite
        │
        ├── Regex/LLM parser (parse only, never executes payments)
        ├── LocalMockCustomerRepository
        ├── PreviewEmailService → email_previews/
        ├── simulate-payment / simulate-time (DEMO_MODE)
        └── Optional: blockchain event scan → InvoicePaymentRouter
```

**Security boundaries:**
- LLM only parses text; never sends email or submits transactions.
- Frontend cannot mark invoices paid — only blockchain events or `simulate-payment` (demo).
- Admin routes require `X-API-Key` header.

---

## API endpoints

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/health` | No |
| GET | `/api/dashboard/summary` | API key |
| GET/POST | `/api/customers` | API key |
| GET/POST | `/api/invoices` | API key |
| POST | `/api/invoices/parse-command` | API key |
| GET | `/api/invoices/{id}` | API key |
| GET | `/api/invoices/by-token/{token}/payment-page` | No |
| POST | `/api/invoices/{id}/send` | API key |
| POST | `/api/invoices/{id}/simulate-payment` | API key + DEMO_MODE |
| POST | `/api/invoices/{id}/simulate-time` | API key |
| POST | `/api/invoices/{id}/send-reminder` | API key |
| POST | `/api/blockchain/scan` | API key |
| GET | `/api/activity` | API key |

---

## Smart contracts

Located in [`contracts/`](contracts/).

```bash
cd contracts
forge install foundry-rs/forge-std OpenZeppelin/openzeppelin-contracts --no-commit
forge test -vv
```

Deploy to Base Sepolia (optional):

```bash
export RPC_URL=https://sepolia.base.org
export PRIVATE_KEY=your_testnet_key   # never commit
forge script script/Deploy.s.sol --rpc-url $RPC_URL --broadcast
```

Set `PAYMENT_CONTRACT_ADDRESS` and `USDC_CONTRACT_ADDRESS` in `.env`.

---

## Tests

```bash
# Backend smoke tests
cd apps/api && .venv/bin/pytest tests -v

# Smart contract tests (requires Foundry)
cd contracts && forge test -vv
```

---

## Environment variables

See [`.env.example`](.env.example). Prototype minimum:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEMO_MODE` | `true` | Enable simulate endpoints |
| `API_KEY` | `dev-key` | Admin route auth |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend → API |
| `NEXT_PUBLIC_DEMO_MODE` | `true` | Show demo buttons |

---

## Known limitations (prototype v0)

- Single merchant, dev API key auth only
- Local mock customers — no Google Sheets yet
- Email previews only — no SMTP delivery
- Reminders via manual/simulate-time — no background scheduler
- Blockchain scan is manual — no continuous polling
- Regex parser handles demo phrasing; free-form NL needs LLM key
- SQLite — not production-ready

---

## Prototype checklist

- [x] Dashboard with stats, chart, activity feed
- [x] Natural-language invoice creation (Daniel Tan demo command)
- [x] Customer directory lookup (Daniel Tan)
- [x] Invoice INV-0001 sequential numbering
- [x] Public payment page with QR code
- [x] Email preview generation
- [x] Simulate payment → Paid status + tx hash
- [x] Simulate time → Overdue + reminder
- [x] InvoicePaymentRouter contract + Foundry tests
- [x] Seed data (3 customers, 3 invoices)
- [x] Backend smoke tests

---

## Troubleshooting

**Dashboard shows connection error** — Ensure API is running on port 8000 and `NEXT_PUBLIC_API_KEY` matches `API_KEY`.

**401 on API calls** — Set `X-API-Key: dev-key` (handled automatically by frontend).

**Seed says already seeded** — Delete `apps/api/settleflow.db` and re-run `python scripts/seed.py`.

**Simulate payment 403** — Set `DEMO_MODE=true` in `apps/api/.env`.

---

Built for hackathon demo. Testnet funds only.
