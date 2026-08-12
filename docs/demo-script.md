# SettleFlow — demo script

## Setup (before judges arrive)

Four terminals. Start them in this order.

```bash
# Terminal 1 — local chain (do this first, keep it running)
cd contracts
anvil

# Terminal 2 — deploy contracts to it (only needed once per anvil restart;
# addresses are deterministic and already match apps/api/.env)
cd contracts
PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
  forge script script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 --broadcast

# Terminal 3 — API
cd apps/api
.venv\Scripts\activate    # or source .venv/bin/activate on macOS/Linux
$env:PYTHONUTF8 = "1"     # Windows only: without this, apostrophes/dashes in
                           # agent-generated text render as garbled characters
rm -f settleflow.db       # start clean
python scripts/seed.py
uvicorn app.main:app --reload --port 8000

# Terminal 4 — Web
cd apps/web
npm run dev
```

Open http://localhost:3000. Sanity check before judges walk up: click an
existing invoice's **Simulate payment** once — it should flip to Paid with a
real transaction hash within ~2 seconds. If it errors, Anvil or the deploy
step didn't run; redo Terminals 1–2.

---

## The one-line pitch

**"SettleFlow lets an AI write your invoices, but it can never touch your
money — only a real blockchain transaction can mark one paid."**

That boundary is the whole point. Say it early, then prove it twice: once on
the payment side, once on the collections side.

---

## Script (~2 minutes)

**0:00 — Dashboard**
"SettleFlow is automated stablecoin invoice collection for Singapore
freelancers billing overseas clients. One glance answers three questions:
who owes me, who's late, did it land."

**0:12 — Create invoice**
Click **Collect payment**. Paste:
`Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.`
Click **Parse command**. "The model only extracts fields — customer, amount,
description, due date. It never sends money and never marks anything paid;
that's a hard boundary in the code, not a policy."

**0:30 — Customer match + create**
"Daniel Tan matched from the customer directory." Click **Create invoice**.
"That also just registered a payment request on a live blockchain — not a
database flag, an actual transaction."

**0:45 — Payment page**
Open the payment link. "This is what Daniel sees — no account, no jargon,
just what's owed and how to pay it."

**0:55 — Real settlement**
Back on invoice detail, click **Simulate payment**. "This is the moment that
matters: that click just minted test USDC, approved the router contract, and
called `payInvoice` for real. The backend didn't take my word for it — it
scanned the chain, saw the `InvoicePaid` event, and only then flipped the
status." *(Optionally show the transaction hash / `cast receipt` in a
terminal for a skeptical judge.)*

**1:15 — Collections agent**
Go to Overview. Pick a pending invoice, click **Simulate time** a couple of
times to push it past due. "Now watch the agent, not me, handle the
follow-up." Click **Run collections agent**. "It just reviewed every overdue
invoice and drafted a reminder — friendly at day one, firmer as it ages,
final notice past a week. No one clicked send. Click it again a few more
times on the same invoice to watch the tone escalate from friendly to firm."

**1:45 — Wrap**
"Two things are real here, not simulated: the settlement is a genuine
on-chain transaction, and the collections follow-up runs itself. The model
touches neither — it only ever reads and drafts. That's the product: an AI
that manages collections without ever being trusted with the money."
