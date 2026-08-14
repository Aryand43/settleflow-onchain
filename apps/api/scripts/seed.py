"""Seed SettleFlow prototype demo data.

Everything is owned by one demo freelancer. Signing in as them shows the
populated dashboard; anyone who signs up fresh gets an empty one.

Set DEMO_CUSTOMER_EMAIL to your own inbox to make the seeded customers
reachable — with SMTP configured, reminders then actually arrive somewhere you
can open on stage. The default @example.com addresses hard-bounce.
"""

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db
from app.deps import DEMO_USER_EMAIL
from app.models.activity import ActivityEvent, EventType
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus, on_chain_invoice_id
from app.services.auth import create_user, get_user_by_email
from app.services.invoice import sync_invoice_counter

DEMO_PASSWORD = "settleflow"


def _customer_email(slot: str, fallback: str) -> str:
    """Every seeded customer gets DEMO_CUSTOMER_EMAIL when it's set, so a live
    SMTP demo lands in one inbox you control rather than bouncing."""
    override = os.environ.get("DEMO_CUSTOMER_EMAIL", "").strip()
    if not override:
        return fallback
    if "@" not in override:
        return fallback
    local, _, domain = override.partition("@")
    # Gmail sub-addressing keeps the three customers distinguishable in one inbox.
    return f"{local}+{slot}@{domain}"


def seed() -> None:
    init_db()
    db = SessionLocal()

    try:
        demo_user = get_user_by_email(db, DEMO_USER_EMAIL)
        if demo_user is None:
            demo_user = create_user(
                db,
                email=DEMO_USER_EMAIL,
                password=DEMO_PASSWORD,
                name="Alex Chen",
                business_name="Alex Chen Design",
                wallet_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            )
            print(f"Created demo account: {DEMO_USER_EMAIL} / {DEMO_PASSWORD}")

        if db.query(Customer).filter(Customer.owner_id == demo_user.id).count() > 0:
            print("Database already seeded.")
            return

        customers = [
            Customer(
                owner_id=demo_user.id,
                name="Daniel Tan",
                email=_customer_email("daniel", "daniel@example.com"),
                wallet_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
                company="Tan Design",
            ),
            Customer(
                owner_id=demo_user.id,
                name="Sarah Lim",
                email=_customer_email("sarah", "sarah@example.com"),
                wallet_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
                company="Lim Studio",
            ),
            Customer(
                owner_id=demo_user.id,
                name="Marcus Koh",
                email=_customer_email("marcus", "marcus@example.com"),
                wallet_address="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
                company="Koh Analytics",
            ),
        ]
        db.add_all(customers)
        db.commit()
        for c in customers:
            db.refresh(c)

        today = date.today()
        wallet = demo_user.wallet_address

        def invoice(number: str, **kwargs) -> Invoice:
            return Invoice(
                owner_id=demo_user.id,
                invoice_number=number,
                merchant_wallet=wallet,
                currency="USDC",
                payment_url=f"http://localhost:3000/pay/demo-{number.lower()}-token",
                on_chain_invoice_id=on_chain_invoice_id(demo_user.id, number),
                **kwargs,
            )

        invoices = [
            invoice(
                "INV-0001",
                customer_id=customers[0].id,
                amount=100.0,
                amount_wei_or_base_units=100_000_000,
                description="Website redesign",
                due_date=today + timedelta(days=7),
                status=InvoiceStatus.pending.value,
                payment_token="demo-pending-token",
            ),
            invoice(
                "INV-0002",
                customer_id=customers[1].id,
                amount=250.0,
                amount_wei_or_base_units=250_000_000,
                description="Brand identity package",
                due_date=today - timedelta(days=10),
                status=InvoiceStatus.paid.value,
                payment_token="demo-paid-token",
                blockchain_tx_hash="0x" + "b" * 64,
                paid_at=datetime.utcnow() - timedelta(days=5),
            ),
            invoice(
                "INV-0003",
                customer_id=customers[2].id,
                amount=500.0,
                amount_wei_or_base_units=500_000_000,
                description="Data dashboard build",
                due_date=today - timedelta(days=3),
                status=InvoiceStatus.overdue.value,
                payment_token="demo-overdue-token",
                reminder_count=1,
            ),
        ]
        # The seeded payment_urls above are placeholders; point them at the real
        # tokens so the links on the dashboard actually open.
        for inv in invoices:
            inv.payment_url = f"http://localhost:3000/pay/{inv.payment_token}"

        db.add_all(invoices)
        db.commit()

        events = [
            ActivityEvent(invoice_id=invoices[0].id, event_type=EventType.invoice_created.value, message="Invoice INV-0001 created"),
            ActivityEvent(invoice_id=invoices[1].id, event_type=EventType.invoice_created.value, message="Invoice INV-0002 created"),
            ActivityEvent(invoice_id=invoices[1].id, event_type=EventType.payment_confirmed.value, message="Payment confirmed for INV-0002"),
            ActivityEvent(invoice_id=invoices[2].id, event_type=EventType.invoice_created.value, message="Invoice INV-0003 created"),
            ActivityEvent(invoice_id=invoices[2].id, event_type=EventType.invoice_overdue.value, message="Invoice INV-0003 marked overdue"),
            ActivityEvent(invoice_id=invoices[2].id, event_type=EventType.reminder_sent.value, message="Reminder sent for INV-0003", metadata_json={"rule": "overdue_3"}),
        ]
        db.add_all(events)
        db.commit()

        # The invoice numbers above are hand-written, so the counter still
        # points at INV-0001. Move it past them or the first invoice created
        # through the API collides with seeded data.
        next_value = sync_invoice_counter(db, demo_user.id)

        print(
            f"Seed complete: 3 customers, 3 invoices, activity events. "
            f"Next invoice number: INV-{next_value:04d}."
        )
        print(f"Sign in at http://localhost:3000/login as {DEMO_USER_EMAIL} / {DEMO_PASSWORD}")
        print(f"Seeded customer emails: {', '.join(c.email for c in customers)}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
