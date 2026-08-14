# SettleFlow

**Automated invoice collection for the global stablecoin economy.**

SettleFlow is a hackathon prototype that helps Singapore-based freelancers collect cross-border invoice payments using stablecoins. Type a natural-language command, create an invoice, share a payment link, and track status on a merchant dashboard. Ask the overview or payments chat about live invoice data — the model answers, it never marks anything paid.

> **Testnet demo only.** No real funds. `DEMO_MODE=true` by default.

---

## Repository layout

```
settleflow-onchain/
├── apps/
│   ├── api/                      FastAPI + SQLAlchemy (Dockerfile)
│   │   ├── app/
│   │   │   ├── main.py           App, CORS, routers
│   │   │   ├── config.py         Settings from apps/api/.env
│   │   │   ├── database.py       SQLite default / Postgres via DATABASE_URL
│   │   │   ├── models/           User, invoice, customer, activity, negotiation
│   │   │   ├── routers/          health, auth, customers, invoices, dashboard,
│   │   │   │                     blockchain, agent, chat
│   │   │   ├── services/         auth, parser, invoice, blockchain, reminders,
│   │   │   │                     email, negotiation, llm, chat
│   │   │   ├── repositories/     Local mock customer directory
│   │   │   └── schemas/
│   │   ├── scripts/seed.py       Demo account + 3 customers, 3 invoices
│   │   └── tests/                Smoke tests (never hit a hosted DB)
│   └── web/                      Next.js 14 App Router (Dockerfile)
│       └── src/
│           ├── app/              /  /login  /signup  /dashboard
│           │                     /customers  /invoices  /invoices/new
│           │                     /invoices/[id]  /pay/[token]
│           ├── components/       AppShell, ChatPanel, StatusBadge, …
│           └── lib/              api.ts, auth.tsx, contracts.ts
├── contracts/                    Foundry
│   ├── src/                      InvoicePaymentRouter.sol, MockUSDC.sol
│   ├── test/
│   └── script/Deploy.s.sol
├── docs/                         demo-script.md, demo-video.md
├── PRODUCT.md
├── docker-compose.yml            api + web (+ optional anvil/contracts)
├── Makefile                      install / seed / dev / test / up / down
└── .env.example                  Copy to apps/api/.env, apps/web/.env.local,
                                  or the repo root for Docker Compose
```

Local secrets live in `apps/api/.env` and `apps/web/.env.local` (gitignored). Never commit `LLM_API_KEY`.

---

## Quick start (5 minutes)

### Prerequisites

- Node.js 18+ and Python 3.9+ — or just Docker, see
  [Running in Docker](#running-in-docker)

### Setup

```bash
git clone https://github.com/Aryand43/settleflow-onchain.git
cd settleflow-onchain

# Backend
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env.example .env
# Optional: set LLM_API_KEY in apps/api/.env for free-form parsing + chat

# Frontend
cd ../web
npm install
cp ../../.env.example .env.local
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

Open [http://localhost:3000](http://localhost:3000) and sign in as
`demo@settleflow.app` / `settleflow`, or create your own account — a new signup
starts with an empty dashboard.

Or from repo root: `make seed` then `make dev`.

---

## Demo script

Live walkthrough with talking points: [`docs/demo-script.md`](docs/demo-script.md).
Recording a video instead: [`docs/demo-video.md`](docs/demo-video.md).
Short version:

1. Sign in as the demo account, or sign up and add a customer at
   **/customers** (one form, or a CSV drop).
2. Create an invoice from a plain-English command — the model only parses; it
   never sends money or marks anything paid.
3. Open the payment link, then click **Simulate payment** — a genuine
   blockchain transaction executes (mint → approve → `payInvoice`), and the
   backend only flips the invoice to Paid after observing the on-chain
   `InvoicePaid` event.
4. Click **Simulate time** on an overdue invoice, then **Run collections
   agent** on the dashboard — it writes an escalating reminder (friendly →
   firm → final notice) for every overdue invoice automatically, no manual
   send required. With SMTP configured those really arrive; without it they
   land in `email_previews/`.
5. On Overview, ask **What's my collection rate?** or **Who is late?** On
   Invoices, ask **Which invoices are unpaid?** Chat is read-only: it cannot
   mark paid or move funds. Needs `LLM_API_KEY` in `apps/api/.env`.

---

## Architecture

```
Merchant Dashboard (Next.js)
  /                 Landing page (signed out) — no shell
  /login /signup    Account access; JWT stored client-side
  /dashboard        Overview + collections chat
  /customers        Directory: add one, or import a CSV
  /invoices         List + payments chat
  /invoices/new     NL collect-payment command
  /invoices/[id]    Detail, QR, demo controls
  /pay/[token]      Public payer page (no merchant shell)
        │
        ▼
   FastAPI Backend ── SQLite (default) / Supabase Postgres
        │
        ├── Regex/LLM parser (parse only, never executes payments)
        ├── Chat (scope=overview | payments) — answers from a live DB snapshot
        ├── Customer directory (manual add + CSV import), per account
        ├── Email: SmtpEmailService when configured, else preview HTML files
        ├── Collections agent (escalating reminders, never marks paid)
        ├── Negotiation agent (capped due-date extensions on the pay page)
        ├── simulate-payment / simulate-time (DEMO_MODE, real chain tx when configured)
        └── Blockchain event scan → InvoicePaymentRouter (Anvil devnet by default, Base Sepolia optional)
```

**Account model:** every customer and invoice belongs to one freelancer. A new
signup gets an empty dashboard; invoice numbering restarts at INV-0001 per
account, and the on-chain invoice id is salted with the owner so two accounts'
INV-0001 don't collide on the router. Cross-account reads return 404, not 403 —
a 403 would confirm the record exists.

**Security boundaries:**
- The LLM parses commands and answers read-only questions. It never sends email, never submits a transaction, and never marks an invoice paid.
- Collections agent only drafts and sends reminder emails; it has no code path to mark an invoice paid or move funds.
- Frontend cannot mark invoices paid — only an observed on-chain event flips status (`simulate-payment` triggers a real transaction in DEMO_MODE, then waits for the chain event like production would).
- Dashboard routes require a per-user JWT (`Authorization: Bearer …`). `X-API-Key` still works but resolves to the demo account only — it's for seed scripts and curl, not a shared production secret.
- `LLM_API_KEY` and `SMTP_PASSWORD` stay on the API; neither is ever a `NEXT_PUBLIC_*` variable.

---

## API endpoints

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/health` | No |
| POST | `/api/auth/signup` | No |
| POST | `/api/auth/login` | No |
| GET | `/api/auth/me` | Session |
| GET | `/api/dashboard/summary` | Session |
| GET/POST | `/api/customers` | Session |
| POST | `/api/customers/import` | Session (CSV upload) |
| DELETE | `/api/customers/{id}` | Session |
| GET/POST | `/api/invoices` | Session |
| POST | `/api/invoices/parse-command` | Session |
| GET | `/api/invoices/{id}` | Session |
| GET | `/api/invoices/by-token/{token}/payment-page` | No |
| GET/POST | `/api/invoices/by-token/{token}/messages` | No |
| GET | `/api/invoices/{id}/messages` | Session |
| GET | `/api/invoices/{id}/activity` | Session |
| POST | `/api/invoices/{id}/send` | Session |
| POST | `/api/invoices/{id}/simulate-payment` | Session + DEMO_MODE |
| POST | `/api/invoices/{id}/simulate-time` | Session |
| POST | `/api/invoices/{id}/send-reminder` | Session |
| POST | `/api/blockchain/scan` | Session |
| POST | `/api/agent/run-collections` | Session |
| GET | `/api/activity` | Session |
| GET | `/api/chat/status` | Session |
| POST | `/api/chat` | Session (`scope`: `overview` or `payments`) |

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

## Accounts

Sign up at `/signup`, or use the seeded demo account:

```
demo@settleflow.app / settleflow
```

Anyone who signs up gets an empty dashboard of their own — their own customer
directory, their own invoices numbered from INV-0001, their own collections
agent. Nothing is shared between accounts.

`scripts/seed.py` creates the demo account if it's missing and is safe to re-run.

---

## Email delivery

Reminders and invoice emails go out over SMTP when it's configured, and are
written to `apps/api/email_previews/*.html` when it isn't. Same code path either
way — see `get_email_service()`.

For Gmail:

1. The sending account needs **2-Step Verification** on.
2. Create an App Password at <https://myaccount.google.com/apppasswords>. The
   normal account password will not work — Google blocked that in 2022.
3. Put the 16 characters in `SMTP_PASSWORD` in `apps/api/.env` and restart.

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=<16-char app password>
EMAIL_FROM=you@gmail.com
```

`EMAIL_FROM` must match the authenticated account or Gmail rejects the message.
Free accounts cap out around 500 recipients a day.

Notes:

- A blank `SMTP_PASSWORD` counts as unconfigured, so the default state stays on
  preview files rather than attempting a send that can't authenticate. The
  dashboard reflects this: the buttons read **Generate invoice email** rather
  than **Send**, with a note explaining why.
- `GET /api/email/status` reports whether delivery is live and from which
  address.
- **The test suite never sends.** `tests/conftest.py` blanks `SMTP_*` before
  anything imports the config, and `pytest_configure` fails the run if delivery
  is somehow still configured — otherwise `pytest` would put real mail in real
  inboxes.
- A failed send is never silent and never fatal: the HTML is still written, and
  the activity timeline records `FAILED to send` with the SMTP error rather than
  claiming a delivery that didn't happen.
- Seeded customers use `@example.com` addresses, which bounce. Set
  `DEMO_CUSTOMER_EMAIL=you@gmail.com` before seeding to point all three at your
  own inbox using `+tags`, so a live email demo actually lands somewhere.

---

## Running in Docker

Only Docker required — no Python, no Node, no virtualenv.

```bash
cp .env.example .env      # optional; sensible defaults apply without it
docker compose up --build -d
docker compose run --rm api python scripts/seed.py
```

Open <http://localhost:3000> and sign in as `demo@settleflow.app` / `settleflow`.
`make up` and `make docker-seed` wrap the same two commands.

Two containers: `api` (FastAPI on 8000, healthchecked) and `web` (Next.js
standalone on 3000, held back until the API reports healthy). Both run as
non-root.

### Configuration

**All API configuration lives in `apps/api/.env`** — the api container reads
that same file via `env_file`, so `uvicorn` and Docker behave identically.
`DATABASE_URL`, `LLM_API_KEY`, `SMTP_*` and the chain variables all belong
there and nowhere else.

The root `.env` is only for the web image's build args, because
`NEXT_PUBLIC_*` is compiled into the JS bundle rather than read at runtime.

Sanity-check what the container actually got:

```bash
docker compose config | grep -E "DATABASE_URL|LLM_API_KEY|SMTP_HOST"
```

Everything is optional. With no `apps/api/.env` at all you get SQLite on a
named volume, preview-file email, and no chain — enough to demo the whole
product except real settlement, straight from a fresh clone.

| Set this | To get |
|----------|--------|
| `DATABASE_URL` | Supabase Postgres instead of the container's SQLite |
| `SMTP_*`, `EMAIL_FROM` | Real reminder emails instead of preview files |
| `LLM_API_KEY` | Free-form parsing and the merchant chat |
| `JWT_SECRET` | Anything not on your laptop **must** set this |

Two gotchas worth knowing before you debug something for twenty minutes:

- **`NEXT_PUBLIC_API_URL` is baked in at image build time**, not read at
  startup. It has to be the URL *the browser* uses, so it stays
  `http://localhost:8000` even though the containers talk to each other by
  service name. Change it and you must `docker compose build web`, not just
  restart.
- **An empty environment variable counts as unset.** Compose writes
  `CHAIN_ID: ""` for anything the host hasn't set; `Settings` drops blanks so
  each field falls back to its own default rather than failing to parse.

### Volumes

- `api-data` (named volume) — the SQLite file, so the demo survives a restart.
  Unused when `DATABASE_URL` points at Postgres.
- `./apps/api/email_previews` (bind mount) — generated reminder HTML, openable
  from the host.

### Local chain, for the real-settlement demo

An opt-in profile replaces the manual Anvil-and-forge dance:

```bash
docker compose --profile chain up -d anvil       # or: make chain-up
docker compose --profile chain run --rm contracts # or: make chain-deploy
```

The second command installs the Solidity dependencies, deploys `MockUSDC` and
`InvoicePaymentRouter`, and prints their addresses. Put them in `.env` — note
`RPC_URL` uses the *service name*, since the API reaches Anvil over the compose
network rather than through your host's port mapping:

```
CHAIN_ID=31337
RPC_URL=http://anvil:8545
PAYMENT_CONTRACT_ADDRESS=<InvoicePaymentRouter from the deploy output>
USDC_CONTRACT_ADDRESS=<MockUSDC from the deploy output>
MERCHANT_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
DEMO_PAYER_PRIVATE_KEY=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
```

Then `docker compose up -d api`. The payment page should report
`chain_configured: true`, and **Simulate payment** produces a genuine
transaction hash instead of the `0xaaaa…` placeholder.

Anvil's port 8545 is also published to the host, so `cast` works from your
machine if you have Foundry installed.

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
| `API_KEY` | `dev-key` | Resolves to the demo account for scripts and curl |
| `JWT_SECRET` | `dev-secret-change-me` | Signs dashboard sessions — **must** be set off localhost |
| `DATABASE_URL` | `sqlite:///./settleflow.db` | SQLite by default, Supabase Postgres optional |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend → API |
| `NEXT_PUBLIC_DEMO_MODE` | `true` | Show demo buttons |
| `LLM_API_KEY` | (empty) | OpenAI-compatible key for parsing + merchant chat |
| `LLM_MODEL` | `gpt-4.1-mini` | Chat/completions model (fallbacks if the project blocks it) |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API root |
| `SMTP_HOST` | (empty) | Blank = write preview files; set = really send |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | (empty) | Gmail address + **App Password** |
| `EMAIL_FROM` | (empty) | Must match the authenticated SMTP account |
| `DEMO_CUSTOMER_EMAIL` | (empty) | Points seeded customers at one real inbox |

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

- Sessions are JWTs in localStorage — fine for a prototype, not a bank
- No email verification or password reset on signup
- Customer directory is manual entry or CSV — no Google Sheets sync
- Collections agent runs on click, not a cron — same as `simulate-time`, it's what a scheduled job would call in production
- Blockchain scan runs after each simulated payment, and can also be triggered manually — no continuous polling yet
- Default chain is a local Anvil devnet, not a public testnet — same contracts, same real transactions, just not independently verifiable by a judge without running Anvil themselves; a Base Sepolia deploy is one `forge script` away (see Smart contracts section)
- Regex parser handles demo phrasing; free-form NL and chat need `LLM_API_KEY`
- Chat is in-memory in the browser — refresh clears the thread; nothing is persisted
- SQLite by default; Supabase Postgres is a `DATABASE_URL` swap away (see above)
- No migrations — `create_all` builds the schema but never alters it

---

## Prototype checklist

- [x] Dashboard with stats, chart, activity feed
- [x] Natural-language invoice creation (Daniel Tan demo command)
- [x] Sign up / sign in, one private workspace per freelancer
- [x] Customers page — add manually or import a CSV, per account
- [x] Invoice INV-0001 sequential numbering (counter row, safe under concurrent creates)
- [x] Public payment page with QR code
- [x] Real email over SMTP when configured; HTML previews when not
- [x] Invoice creation registers a real payment request on-chain
- [x] Simulate payment → genuine on-chain transaction, status flips only after the chain event is observed
- [x] Simulate time → Overdue, escalating multiple clicks
- [x] Collections agent (`/api/agent/run-collections`) — auto-drafts escalating reminders (friendly → firm → final) for overdue invoices, dashboard trigger on Overview
- [x] InvoicePaymentRouter contract + Foundry tests (7/7 passing)
- [x] Overview chat (`scope=overview`) and invoices payments chat (`scope=payments`)
- [x] Seed data (demo account, 3 customers, 3 invoices)
- [x] Backend smoke tests, including cross-account isolation

---

## Troubleshooting

**Dashboard shows connection error** — Ensure the API is running on port 8000 and `NEXT_PUBLIC_API_URL` points at it.

**Redirected to /login immediately** — The session expired or the database was reset out from under it. Sign in again; `seed.py` recreates the demo account.

**Reminders say "drafted", not "sent"** — `SMTP_PASSWORD` is blank, so the app is writing preview files instead of sending. See [Email delivery](#email-delivery). Check what the app thinks with `GET /api/email/status`; the invoice page also shows a note above the send buttons when delivery isn't configured.

**In Docker: `Network is unreachable` connecting to Supabase** — you're on the direct `db.<ref>.supabase.co` host, which is IPv6-only. Your laptop has IPv6; the container's bridge network does not. Switch `DATABASE_URL` to the **Session pooler** host (`aws-0-<region>.pooler.supabase.com`, username `postgres.<ref>`), which is IPv4.

**In Docker: config set in `apps/api/.env` seems ignored** — it shouldn't be; the container reads that file directly. Confirm with `docker compose config | grep LLM_API_KEY`, and remember `docker compose up` reuses the last built image — use `--build` (or `make up`) after changing anything that's baked in at build time.

**Docker: dashboard loads but every request fails** — `NEXT_PUBLIC_API_URL` was baked in wrong at build time. It must be the URL your browser uses (`http://localhost:8000`), not a compose service name. Fix `.env` and rebuild: `docker compose build web`.

**Docker: `dependency failed to start: container ... is unhealthy`** — the API crashed on boot. `docker compose logs api` has the traceback; a bad `DATABASE_URL` is the usual cause.

**"Failed to fetch" on the payer page** — the API returned an unhandled 500, which carries no CORS headers, so the browser hides the real error. `docker compose logs api` has the traceback. The usual cause was a contract revert; payment now registers the invoice on-chain on demand and returns a readable 502 instead.

**Docker: Simulate payment still returns `0xaaaa…`** — the chain vars aren't reaching the container. Check `docker compose config` renders them, and that `RPC_URL` is `http://anvil:8545` rather than `localhost`.

**401 on API calls** — The dashboard sends a session token automatically; sign in again if it expired. For curl and scripts, `X-API-Key: dev-key` resolves to the demo account.

**Seed says already seeded** — Delete `apps/api/settleflow.db` and re-run `python scripts/seed.py`. On Supabase, truncate the tables from the SQL editor instead.

**`ModuleNotFoundError: psycopg`** — Re-run `pip install -r requirements.txt`; the Postgres driver was added alongside Supabase support.

**Connection times out on Supabase** — You're likely on the direct connection (`db.<ref>.supabase.co`), which is IPv6-only on the free tier. Use the pooler host from the Session pooler tab.

**Simulate payment 403** — Set `DEMO_MODE=true` in `apps/api/.env`.

**Chat says add an API key** — Set `LLM_API_KEY` in `apps/api/.env` (not the frontend env) and restart uvicorn. Settings are read at process start.

**Chat 502 / LLM 403** — The API host must be able to reach `LLM_BASE_URL`. Project keys sometimes block `gpt-4o-mini`; the backend falls back to `gpt-4.1-mini` and other current chat models.

---

Built for hackathon demo. Testnet funds only.
