"""Seed SettleFlow prototype demo data."""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db
from app.models.activity import ActivityEvent, EventType
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus


def seed() -> None:
    init_db()
    db = SessionLocal()

    try:
        if db.query(Customer).count() > 0:
            print("Database already seeded.")
            return

        customers = [
            Customer(
                name="Daniel Tan",
                email="daniel@example.com",
                wallet_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
                company="Tan Design",
            ),
            Customer(
                name="Sarah Lim",
                email="sarah@example.com",
                wallet_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
                company="Lim Studio",
            ),
            Customer(
                name="Marcus Koh",
                email="marcus@example.com",
                wallet_address="0x90F79bf6EB2c4f870365E785982E1f101E93b906",
                company="Koh Analytics",
            ),
        ]
        db.add_all(customers)
        db.commit()
        for c in customers:
            db.refresh(c)

        today = date.today()
        merchant_wallet = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

        invoices = [
            Invoice(
                invoice_number="INV-0001",
                customer_id=customers[0].id,
                merchant_wallet=merchant_wallet,
                amount=100.0,
                currency="USDC",
                amount_wei_or_base_units=100_000_000,
                description="Website redesign",
                due_date=today + timedelta(days=7),
                status=InvoiceStatus.pending.value,
                payment_token="demo-pending-token",
                payment_url="http://localhost:3000/pay/demo-pending-token",
                on_chain_invoice_id="0x" + __import__("hashlib").sha256(b"INV-0001").hexdigest(),
            ),
            Invoice(
                invoice_number="INV-0002",
                customer_id=customers[1].id,
                merchant_wallet=merchant_wallet,
                amount=250.0,
                currency="USDC",
                amount_wei_or_base_units=250_000_000,
                description="Brand identity package",
                due_date=today - timedelta(days=10),
                status=InvoiceStatus.paid.value,
                payment_token="demo-paid-token",
                payment_url="http://localhost:3000/pay/demo-paid-token",
                blockchain_tx_hash="0x" + "b" * 64,
                paid_at=datetime.utcnow() - timedelta(days=5),
                on_chain_invoice_id="0x" + __import__("hashlib").sha256(b"INV-0002").hexdigest(),
            ),
            Invoice(
                invoice_number="INV-0003",
                customer_id=customers[2].id,
                merchant_wallet=merchant_wallet,
                amount=500.0,
                currency="USDC",
                amount_wei_or_base_units=500_000_000,
                description="Data dashboard build",
                due_date=today - timedelta(days=3),
                status=InvoiceStatus.overdue.value,
                payment_token="demo-overdue-token",
                payment_url="http://localhost:3000/pay/demo-overdue-token",
                reminder_count=1,
                on_chain_invoice_id="0x" + __import__("hashlib").sha256(b"INV-0003").hexdigest(),
            ),
        ]
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
        print("Seed complete: 3 customers, 3 invoices, activity events.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
