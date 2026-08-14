# SettleFlow — demo video script

A ~3:10 screen recording. For the live, in-person walkthrough see
[`demo-script.md`](demo-script.md) — this one is written for a camera: fixed
beats, narration to read aloud, and the parts you can cut.

The story is one invoice's whole life: created by a sentence, negotiated by an
agent, settled on a blockchain, chased automatically when it goes late.

---

## Pre-flight

**Do this the day before, not ten minutes before.** Three of these have bitten
this project already.

### 1. The chain must be running, or the best shot in the video doesn't exist

**The chain is now configured** in `apps/api/.env` — Anvil's deterministic
addresses, which stay the same across restarts. You just have to start the
chain and redeploy each time Docker's anvil container is recreated:

```bash
docker compose --profile chain up -d anvil
docker compose --profile chain run --rm contracts
docker compose up -d api          # picks up a fresh chain
```

If those variables are ever commented out again, **Simulate payment** silently
falls back to a fake `0xaaaa…` hash — the demo still "works", which is exactly
what makes it dangerous to discover while recording. The manual path:

```bash
# Terminal 1 — leave running
cd contracts && anvil

# Terminal 2 — once per anvil restart
cd contracts
forge install foundry-rs/forge-std OpenZeppelin/openzeppelin-contracts --no-commit  # first time only
PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
  forge script script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
```

Copy the two addresses **from the forge output** into `apps/api/.env` — don't
trust remembered values:

```
CHAIN_ID=31337
RPC_URL=http://127.0.0.1:8545
PAYMENT_CONTRACT_ADDRESS=<InvoicePaymentRouter from forge output>
USDC_CONTRACT_ADDRESS=<MockUSDC from forge output>
MERCHANT_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
DEMO_PAYER_PRIVATE_KEY=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
```

Those two keys are Anvil's standard dev accounts #0 (merchant) and #1 (the demo
payer, which is also Daniel Tan's seeded wallet). Anvil prints all ten accounts
and keys on startup — cross-check against that terminal rather than against
this file.

Restart the API after editing. **Verify before recording:** the payment page
should report `chain_configured: true`, and a test payment should return a
`0x…` hash that is *not* all a's:

```bash
curl -s http://localhost:8000/api/invoices/by-token/<token>/payment-page | grep chain_configured
# "chain_configured":true
```

Note `RPC_URL=http://anvil:8545` — the compose service name. Running `uvicorn`
on your laptop instead, it has to be `http://127.0.0.1:8545`; that is the one
setting that differs between the two ways of running.

### 2. Reset the database to clean seed state

The old `rm -f settleflow.db` no longer applies — the app is on Supabase now.

```bash
cd apps/api
.venv/bin/python -c "
from app.database import Base, engine
import app.models
Base.metadata.drop_all(bind=engine)"

# Point the seeded customers at an inbox you can open on camera. Skip this and
# they keep their @example.com addresses, which bounce.
DEMO_CUSTOMER_EMAIL=settleflowhackathon@gmail.com .venv/bin/python scripts/seed.py

.venv/bin/python scripts/check_db.py # 1 user, 3 customers, 3 invoices, 6 events
```

This recreates the demo account, **demo@settleflow.app / settleflow**.

`http://localhost:3000` is now the **marketing page**, not the dashboard. Sign
in at `/login` first and let it land you on `/dashboard`, then start recording —
the first frame should not be a login form you are typing into.

Re-run this between takes. Clean numbers matter — a dashboard reading
`INV-0011` after six rehearsals looks like a test environment, because it is.

### 2b. Confirm email is really sending

**Email delivery is configured** — `settleflowhackathon@gmail.com` with a Gmail
App Password. Reminders genuinely arrive, the activity timeline says **sent
to …**, and the buttons read **Send invoice email** / **Send reminder**.

If that password is ever cleared, the app falls back to writing
`apps/api/email_previews/*.html`, the timeline says **drafted**, and the buttons
relabel themselves **Generate invoice email** / **Generate reminder**. Both
states are demoable — what you must not do is narrate "sent" over a timeline
that reads "drafted". Check which mode you are in before you roll:

```bash
curl -s -H "X-API-Key: dev-key" http://localhost:8000/api/email/status
# {"configured":true,"from_address":"settleflowhackathon@gmail.com"}
```

This is the same in Docker — the api container reads `apps/api/.env`
directly, so there is only one file to get right. Confirm with
`docker compose config | grep SMTP_HOST` if the endpoint says `false`.

### 3. Never let these on camera

- `apps/api/.env` — it holds the live Supabase password, the Gmail App
  Password, and `JWT_SECRET`. Anyone who reads that frame can sign in as any
  account.
- Any terminal where you've pasted the connection string.
- Editor sidebars with `.env` visible in the file tree.
- The signup form mid-type, if you're using a password you reuse anywhere.

Close the API terminal or park it on a scrolled-past screen. If you show the
Supabase dashboard (see the optional shot below), the project ref in the URL is
fine; the password is not.

### 3b. Or skip the terminals entirely

The whole stack runs in Docker now, which is one fewer thing to go wrong on
someone else's laptop:

```bash
docker compose up --build -d
docker compose run --rm api python scripts/seed.py
```

The chain profile works the same way — see the README. The api container reads
`apps/api/.env`, the same file `uvicorn` uses, so there is one place to
configure everything. (The root `.env` only carries the web image's build args,
because `NEXT_PUBLIC_*` is compiled into the bundle rather than read at
runtime.)

One habit worth keeping: **`docker compose up --build`**, or `make up`. Plain
`up` reuses the last built image, and the web bundle really can go stale.

### 4. Recording setup

- 1920×1080, browser at **125% zoom**. Judges may watch this in a small window.
- Hide bookmarks bar, close extra tabs, use a clean profile or incognito.
- Two windows arranged in advance: **merchant dashboard** and **payment page**.
  Switching windows reads as two people; copy-pasting a URL mid-take reads as a
  fumble.
- Do a silent dry run first. The point is to find where the app pauses so you
  can talk over those gaps instead of editing them out.

---

## Shot list

Timings are targets, not a stopwatch. Narration is written to be read at a
normal speaking pace.

### 0:00 — Cold open on the dashboard *(15s)*

**On screen:** Overview page, already loaded. Collected 250, Outstanding 100,
Overdue 500, and the amber past-due banner visible.

> "A Singapore freelancer invoices a client in Jakarta. The money takes three
> days and loses a cut to two banks, and when it's late, chasing it is a job
> nobody wants. SettleFlow is that job, automated — stablecoin rails for the
> money, an AI agent for the chasing."

**Don't** narrate the stat cards. The viewer can read.

### 0:15 — Add a customer *(20s)*

**On screen:** Open **Customers**. Type a name and email into the form and add
it — or drop a CSV, if you'd rather show the import.

> "First, who am I billing. One at a time, or drop in the CSV you exported from
> whatever you're using today. Bad rows get flagged by line; the rest still
> import."

**Why this beat exists:** it's the difference between a demo that works for
anyone and one that works for three hardcoded names. If a judge later types
their own name into the invoice command, the page offers to add them inline —
worth mentioning, and worth doing live if someone asks.

### 0:35 — Create an invoice from a sentence *(30s)*

**On screen:** Click **Collect payment**. Type — don't paste, typing reads as
real — into the command box:

```
Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.
```

Click **Parse command**. Fields populate: Daniel Tan, 100 USDC, website
redesign, due date seven days out.

> "Plain English in. The model's only job is to pull out fields — customer,
> amount, description, due date. It cannot send money and it cannot mark
> anything paid. That's not a rule we wrote in a prompt; there's no code path
> from the parser to either one."

Click **Create invoice**. Land on INV-0004.

> "Creating it also registered the invoice on-chain — a real payment request
> the customer can pay against."

### 1:05 — What the customer sees *(20s)*

**On screen:** Switch to the second window, already on the payment link. Amount,
due date, QR code, merchant wallet.

> "Daniel gets a link. No account, no wallet connect flow, no jargon — what's
> owed, and how to pay it."

### 1:25 — The customer asks for more time *(35s)*

**On screen:** Scroll to the message box. Type: `Can I get 5 more days?`
Click **Send**. The agent's reply appears inline.

> "Here's where most invoicing tools hand you back a support inbox. Daniel asks
> for more time, and the agent answers — it moves the due date five days and
> tells him it's done."

Pause on the reply. Then:

> "But it's working inside a fence. Five days it can approve. Thirty it can't —
> that gets flagged to me instead. It can never reduce the amount, never change
> what's owed on-chain, never mark anything paid. The agent negotiates *time*.
> That's the only lever it has."

**Optional, if the pacing allows:** send `I need 30 days` and show the refusal.
It's the strongest single proof of the boundary — worth the extra 10 seconds if
you have them.

### 2:00 — Real settlement *(30s)*

**On screen:** Back on the merchant window, invoice detail. Click **Simulate
payment**. Let the ~2 seconds of latency sit — that pause is the proof.

> "Now Daniel pays. That click just minted test USDC, approved the router
> contract, and called `payInvoice` — three real transactions on a real chain."

Status flips to Paid, transaction hash appears.

> "And the backend didn't take the frontend's word for it. It scanned the
> chain, found the `InvoicePaid` event, and only then flipped the status.
> Nothing in this system can mark an invoice paid except the chain itself."

**Optional B-roll:** cut to a terminal running `cast receipt <hash>
--rpc-url http://127.0.0.1:8545`. Two seconds on screen. Kills any suspicion
the hash is decorative.

### 2:30 — The agent chases a late invoice *(35s)*

**On screen:** Go to INV-0003 (the seeded 500 USDC overdue one). Click
**Simulate time** twice — each click ages it three more days. Return to
Overview and click **Run collections agent**.

> "Different invoice, three days late. I'll age it a week."

The result banner lists what it sent.

> "One click, and the agent reviewed every overdue invoice and wrote the
> follow-up itself. Tone escalates with age — friendly at day one, firmer after
> three, final notice past a week. Nobody wrote these. Nobody clicked send."

Open the activity timeline to show the reminder entries stacked up.

> "And it still only writes email. Same fence as before — no path to the money."

**If SMTP is live:** cut to the inbox and open the reminder that just arrived.
Five seconds, and it turns "the agent drafted something" into "a real email
reached a real client." This is the biggest upgrade available to this video —
take it if you have the App Password.

**If it isn't:** say **drafted**, never sent, and open the generated HTML from
`apps/api/email_previews/` instead. The timeline on screen says "drafted" too,
so the two match.

### 3:05 — Close *(15s)*

**On screen:** Back to Overview, showing the updated numbers.

> "Two things here are real, not simulated: the settlement is a genuine on-chain
> transaction, and the collections run themselves. The AI touches neither. It
> reads, it writes, it negotiates time — and that's all we ever let it do.
> That's the product: collections you can hand to an agent without handing it
> your money."

---

## Optional shot: a judge signs up

If the video is going somewhere people can act on it, a ten-second cut of
**/signup** is worth including: it shows the product is multi-tenant, not a
single hardcoded workspace. Signup drops you on an empty **/customers** — the
first thing a new freelancer actually needs — and the sidebar header swaps to
their own name and email. Their invoices number from INV-0001, independently of
anyone else's.

Record it as a separate take and cut it in after the landing page, or drop it —
it's the first thing to lose if you're over time.

---

## Optional shot: prove the data is real

If judges are the kind who suspect a hardcoded frontend, a five-second cut to
the **Supabase table editor** with the `invoices` row visible — same invoice
number, same amount — is worth more than a paragraph of narration. Place it
right after the settlement beat.

Have the tab open and scrolled to the right row *before* you record. Hunting
through a dashboard on camera undoes the effect.

---

## Editing notes

- **Cut:** page loads, the seed/reset commands, any typing longer than the
  invoice command, window-switch fumbles.
- **Keep:** the ~2s settlement pause, the agent's reply appearing, the
  collections result banner rendering. Latency you narrate over reads as real;
  latency in silence reads as broken.
- **Captions:** burn in subtitles. Half of hackathon judging happens muted.
- **Zoom in post** on the transaction hash and the agent's reply text — at
  1080p on a laptop both are borderline unreadable.
- **No background music** under narration, or mix it under -20dB. It competes
  with exactly the sentences that carry the argument.

## If something breaks mid-record

- **Payment returns `0xaaaa…`** — Anvil isn't running or `.env` isn't filled in.
  Stop, fix pre-flight step 1, reset the DB, start over. Don't ship the take;
  a fake hash is the one thing a technical judge will catch.
- **Agent reports 0 reminders sent** — that invoice already got a reminder at
  its current tier. Click **Simulate time** twice more to push it to the next
  tier, or reset the DB.
- **Timeline says "FAILED to send"** — the Gmail App Password is wrong or
  expired. The reminder HTML was still written, so you can fall back to the
  preview-file version of the beat without re-recording; just don't say "sent".
- **Kicked to /login mid-take** — the database was reset while the browser held
  an old session. Sign in again; the token is fine, the account it pointed at
  was dropped.
- **A request hangs** — the Supabase connection dropped. The pool reconnects on
  the next request; just retry, and cut the pause.
