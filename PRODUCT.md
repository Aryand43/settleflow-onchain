# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: the merchant** — a Singapore-based independent freelancer or small studio owner invoicing overseas clients. They work alone, handle their own billing between client work, and treat invoicing as overhead they want to finish in under a minute. They arrive at the dashboard to answer one of three questions: *who owes me, who is late, and did that payment land?*

**Secondary: the payer** — the freelancer's client, often outside Singapore, who receives a link and has never used SettleFlow before. They see exactly one surface (`/pay/{token}`), have no account, and need to understand what they owe and how to pay it without instruction.

**Evaluative audience: hackathon judges.** Design honestly for the merchant; when two options are close, pick the one that reads better on a projector during the 90-second demo. Judges are the tiebreaker, never the brief.

## Product Purpose

SettleFlow turns a typed sentence into a collectible invoice that settles in USDC on-chain. The merchant writes `Collect 100 USDC from Daniel Tan for the website redesign, due in 7 days.`, confirms the parsed fields, and gets an invoice number, a shareable payment link, a QR code, and an email preview. When the client pays, the router contract emits an event, the backend observes it, and the invoice flips to Paid with a transaction hash attached.

Success is the merchant never opening a spreadsheet: creation, chasing, and reconciliation all happen on one dashboard, and payment status is something they read rather than something they maintain.

## Positioning

**Natural language in, on-chain settlement out — with the model held strictly to parsing.**

The differentiator is not that an LLM is involved; it is where the LLM is *not*. The parser converts text to structured fields and stops there. It cannot send email, cannot submit a transaction, and cannot mark anything paid. Money moves only through the `InvoicePaymentRouter` contract, and status changes only from an observed on-chain event (or, in demo mode, an explicit `simulate-payment` call). The frontend has no path to mark an invoice paid.

That boundary is the product's credibility: a neighboring "AI invoicing" tool that lets the model act cannot truthfully claim it, and any surface that blurs it undercuts the whole position. Design work should make the boundary visible, not hide it.

## Operating Context

- **Merchant surfaces:** Overview (collected / outstanding / overdue stats, collection chart, activity feed), Invoices list, Collect payment (NL command → parse → confirm → create), Invoice detail (payment URL, QR, simulate payment, simulate time, send reminder).
- **Payer surface:** `/pay/{token}` — public, unauthenticated, single-purpose. No nav shell; `AppShell` deliberately drops out on this route.
- **Rhythm:** creation is bursty (after finishing client work), checking is habitual (a few times a week), chasing is reluctant. The overdue path is the emotionally loaded one — the merchant is asking a client for money.
- **Demo rhythm:** the whole product is exercised in ~90 seconds against seeded data. Sequence is documented in `docs/demo-script.md` and the README.
- **Stack:** Next.js 14 App Router + Tailwind + TanStack Query + Recharts + wagmi/viem (`apps/web`); FastAPI + SQLAlchemy + SQLite (`apps/api`); Foundry contracts (`contracts/`). Geist Sans / Geist Mono are already vendored as local woff files.

## Capabilities and Constraints

**Confirmed capabilities:** sequential invoice numbering (`INV-0001`); regex parser that works with no API key, with optional LLM upgrade; local mock customer directory with name matching; QR + copyable payment URL; email and reminder HTML previews written to `apps/api/email_previews/`; manual blockchain event scan; activity timeline.

**Invoice status vocabulary** (use these words exactly, never invent synonyms): `draft`, `pending`, `partially_paid`, `paid`, `overdue`, `disputed`, `cancelled`. Only `pending`, `paid`, and `overdue` appear in the demo path; the other four exist in the model and any status treatment must accommodate all seven.

**Terminology:** *merchant* (the freelancer), *customer* (the payer), *invoice*, *payment link*, *settlement*. USDC amounts are stored both as a float and as base units.

**Prototype constraints, all currently true:** single merchant; dev API key (`X-API-Key`) auth only; no SMTP — previews only; no background scheduler — reminders are manual or via `simulate-time`; blockchain scan is manual, not polled; SQLite; `DEMO_MODE=true` by default.

**Demo affordances** (`Simulate payment`, `Simulate time`) are real product surface, not debug scaffolding to hide. They are gated on `NEXT_PUBLIC_DEMO_MODE` and must read as deliberate demo controls, visually distinct from actions that represent real money movement.

## Brand Commitments

Name: **SettleFlow**. Existing tagline in metadata: *"Automated invoice collection for the global stablecoin economy."* The README uses a plainer framing: *"Automated stablecoin invoicing."* No logo asset exists beyond an `SF` monogram tile in `AppShell`. No committed palette or type system has been established — the incumbent slate/blue Tailwind defaults are unowned scaffolding, not an identity.

## Evidence on Hand

- Working end-to-end flow across three real apps (web, api, contracts) with passing backend smoke tests and Foundry contract tests.
- `InvoicePaymentRouter.sol` and `MockUSDC.sol` with a deploy script targeting Base Sepolia.
- Generated email and reminder HTML in `apps/api/email_previews/`.
- Seed data: 3 customers (Daniel Tan / Tan Design, Sarah Lim / Lim Studio, Marcus Koh / Koh Analytics) and 3 invoices.

**Fictional — never present as real:** every seeded customer, company, wallet address, invoice, and transaction hash. There are no users, no volume, no testimonials, no press, no pricing, no deployed mainnet address. Do not fabricate any of these, and do not imply production readiness. Testnet only.

## Product Principles

1. **The boundary is the product.** Make it legible that the model only parses and that paid status comes from chain evidence. Never design a surface that implies the app can decide a payment happened.
2. **Answer the three questions above the fold.** Who owes me, who is late, did it land. Every merchant surface earns its place against those.
3. **One sentence beats a form.** The natural-language path is the front door; the structured fields are the confirmation step, not the primary input.
4. **The payer gets no homework.** `/pay/{token}` must be understandable cold, by someone who has never heard of SettleFlow, on a phone, in one screen.
5. **Say testnet plainly.** Demo state and testnet-only are stated in the interface, not buried. Honesty about the prototype's limits is cheaper than a judge discovering them.

## Accessibility & Inclusion

No product-specific standard has been established. Two facts from the domain that future work must respect: status is currently carried by color-coded badges and must never depend on hue alone, and the payer surface will frequently be opened on a phone by someone in another timezone and locale — currency, amount, and due date must survive that.
