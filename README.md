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
export PYTHONUTF8=1   # Windows: prevents Python from misreading source files as cp1252
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

## Demo script

Full walkthrough with talking points: [`docs/demo-script.md`](docs/demo-script.md).
Short version:

1. Create an invoice from a plain-English command — the model only parses; it
   never sends money or marks anything paid.
2. Open the payment link, then click **Simulate payment** — a genuine
   blockchain transaction executes (mint → approve → `payInvoice`), and the
   backend only flips the invoice to Paid after observing the on-chain
   `InvoicePaid` event.
3. Click **Simulate time** on an overdue invoice, then **Run collections
   agent** on the dashboard — it drafts an escalating reminder (friendly →
   firm → final notice) for every overdue invoice automatically, no manual
   send required.

---

## Architecture

```
Merchant Dashboard (Next.js)
        │
        ▼
   FastAPI Backend ── SQLite (default) / Supabase Postgres
        │
        ├── Regex/LLM parser (parse only, never executes payments)
        ├── LocalMockCustomerRepository
        ├── PreviewEmailService → email_previews/
        ├── Collections agent (escalating reminders, never marks paid)
        ├── simulate-payment / simulate-time (DEMO_MODE, real chain tx when configured)
        └── Blockchain event scan → InvoicePaymentRouter (Anvil devnet by default, Base Sepolia optional)
```

**Security boundaries:**
- LLM only parses text; never sends email or submits transactions.
- Collections agent only drafts and sends reminder emails; it has no code path to mark an invoice paid or move funds.
- Frontend cannot mark invoices paid — only an observed on-chain event flips status (`simulate-payment` triggers a real transaction in DEMO_MODE, then waits for the chain event like production would).
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
| POST | `/api/agent/run-collections` | API key |
| GET | `/api/activity` | API key |
| GET | `/api/chat/status` | API key |
| POST | `/api/chat` | API key |

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

The suite always runs against a throwaway local SQLite file, whatever
`DATABASE_URL` says — it drops and recreates every table between cases, so it
must never touch a hosted database. To run it against Postgres deliberately
(worth doing before trusting a schema change on Supabase):

```bash
docker run -d --name settleflow-pg -e POSTGRES_PASSWORD=devpass \
  -e POSTGRES_DB=settleflow -p 55432:5432 postgres:16

TEST_DATABASE_URL=postgresql://postgres:devpass@127.0.0.1:55432/settleflow \
  .venv/bin/pytest tests -q
```

---

## Environment variables

See [`.env.example`](.env.example). Prototype minimum:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEMO_MODE` | `true` | Enable simulate endpoints |
| `API_KEY` | `dev-key` | Admin route auth |
| `DATABASE_URL` | `sqlite:///./settleflow.db` | SQLite by default, Supabase Postgres optional |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend → API |
| `NEXT_PUBLIC_DEMO_MODE` | `true` | Show demo buttons |
| `LLM_API_KEY` | (empty) | OpenAI-compatible key for parsing + merchant chat |

---

## Hosted database (Supabase)

The app runs on SQLite out of the box and needs no database server. To put it on
hosted Postgres instead, only `DATABASE_URL` changes:

1. Supabase dashboard → **Project Settings → Database → Connection string**.
   Take the **Session pooler** URI (port `5432`), not the transaction pooler.
2. Put it in `apps/api/.env`, URL-encoding any `@ : / ? #` in the password:

   ```
   DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
   ```

   The `postgresql://` string Supabase gives you works pasted as-is — the app
   rewrites it onto psycopg 3 and applies hosted-DB pool settings
   (`pool_pre_ping`, a 5-minute recycle, prepared statements disabled so either
   pooler port works).
3. `python scripts/seed.py` — creates the tables and loads demo data.

Notes:

- The tests never touch this. `tests/conftest.py` forces a local
  `test_settleflow.db`, because the suite drops and recreates every table.
- `init_db()` only ever *creates* tables; it will not alter an existing schema.
  Once there's data in Supabase you care about, add Alembic before changing a
  model.
- No Supabase client library or API key is involved — this is a plain Postgres
  connection, so the only secret is the database password in the URL. (The
  anon/service keys are for PostgREST and Auth, which this app doesn't use.)
- Postgres enforces the foreign keys that SQLite quietly ignored, so deleting a
  customer or invoice that still has activity rows now fails instead of leaving
  orphans. Nothing in the app deletes those, but hand-editing data will notice.
- Invoice numbers come from the `invoice_counters` row, not a row count. On a
  database that already holds invoices, the counter is created starting just
  above the highest existing number, so nothing is reissued.

---

## Known limitations (prototype v0)

- Single merchant, dev API key auth only
- Local mock customers — no Google Sheets yet
- Email previews only — no SMTP delivery
- Collections agent runs on click, not a cron — same as `simulate-time`, it's what a scheduled job would call in production
- Blockchain scan runs after each simulated payment, and can also be triggered manually — no continuous polling yet
- Default chain is a local Anvil devnet, not a public testnet — same contracts, same real transactions, just not independently verifiable by a judge without running Anvil themselves; a Base Sepolia deploy is one `forge script` away (see Smart contracts section)
- Regex parser handles demo phrasing; free-form NL needs LLM key
- SQLite by default; Supabase Postgres is a `DATABASE_URL` swap away (see above)
- No migrations — `create_all` builds the schema but never alters it

---

## Prototype checklist

- [x] Dashboard with stats, chart, activity feed
- [x] Natural-language invoice creation (Daniel Tan demo command)
- [x] Customer directory lookup (Daniel Tan)
- [x] Invoice INV-0001 sequential numbering (counter row, safe under concurrent creates)
- [x] Public payment page with QR code
- [x] Email preview generation
- [x] Invoice creation registers a real payment request on-chain
- [x] Simulate payment → genuine on-chain transaction, status flips only after the chain event is observed
- [x] Simulate time → Overdue, escalating multiple clicks
- [x] Collections agent (`/api/agent/run-collections`) — auto-drafts escalating reminders (friendly → firm → final) for overdue invoices, dashboard trigger on Overview
- [x] InvoicePaymentRouter contract + Foundry tests (7/7 passing)
- [x] Seed data (3 customers, 3 invoices)
- [x] Backend smoke tests

---

## Troubleshooting

**Dashboard shows connection error** — Ensure API is running on port 8000 and `NEXT_PUBLIC_API_KEY` matches `API_KEY`.

**401 on API calls** — Set `X-API-Key: dev-key` (handled automatically by frontend).

**Seed says already seeded** — Delete `apps/api/settleflow.db` and re-run `python scripts/seed.py`. On Supabase, truncate the tables from the SQL editor instead.

**`ModuleNotFoundError: psycopg`** — Re-run `pip install -r requirements.txt`; the Postgres driver was added alongside Supabase support.

**Connection times out on Supabase** — You're likely on the direct connection (`db.<ref>.supabase.co`), which is IPv6-only on the free tier. Use the pooler host from the Session pooler tab.

**Simulate payment 403** — Set `DEMO_MODE=true` in `apps/api/.env`.

---

Built for hackathon demo. Testnet funds only.
