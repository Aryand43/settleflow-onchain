from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text, event, inspect, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

INVOICE_NUMBER_PREFIX = "INV-"
# Single-row table, so the counter is always addressed by this id.
INVOICE_COUNTER_ID = 1


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    partially_paid = "partially_paid"
    paid = "paid"
    overdue = "overdue"
    disputed = "disputed"
    cancelled = "cancelled"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    merchant_wallet: Mapped[str] = mapped_column(String(42), nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(16), default="USDC")
    # BigInteger, not Integer: Postgres INTEGER is 32-bit, which at USDC's 6
    # decimals would cap a single invoice at ~2,147 USDC. SQLite ignored the
    # width, so this only becomes a real limit on a hosted Postgres.
    amount_wei_or_base_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=InvoiceStatus.pending.value, index=True)
    payment_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    payment_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    blockchain_tx_hash: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    on_chain_invoice_id: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)

    customer = relationship("Customer", back_populates="invoices")
    activity_events = relationship("ActivityEvent", back_populates="invoice")
    negotiation_messages = relationship(
        "NegotiationMessage", back_populates="invoice", order_by="NegotiationMessage.created_at"
    )


class InvoiceCounter(Base):
    """Hands out the sequential part of INV-0001. A single row, incremented
    under a row lock, so two concurrent invoice creations can't be handed the
    same number — which previously also meant two identical
    `on_chain_invoice_id`s, and the router rejects a duplicate invoice id."""

    __tablename__ = "invoice_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


def parse_invoice_number(invoice_number: str) -> int | None:
    """`INV-0007` -> 7. Returns None for anything not in that shape."""
    if not invoice_number or not invoice_number.startswith(INVOICE_NUMBER_PREFIX):
        return None
    suffix = invoice_number[len(INVOICE_NUMBER_PREFIX) :]
    return int(suffix) if suffix.isdigit() else None


def format_invoice_number(value: int) -> str:
    return f"{INVOICE_NUMBER_PREFIX}{value:04d}"


@event.listens_for(InvoiceCounter.__table__, "after_create")
def _seed_invoice_counter(target, connection, **kw):
    """Creates the counter row as part of the DDL that creates its table, so it
    always exists by the time anything reads it — no get-or-create race on the
    first invoice.

    On a database that predates this table, the counter has to start above the
    invoice numbers already in there; on a fresh one, `invoices` doesn't exist
    yet and it starts at 1."""
    start = 1
    if inspect(connection).has_table("invoices"):
        existing = connection.execute(select(Invoice.invoice_number)).scalars().all()
        # Parsed in Python rather than via max(): the zero padding only sorts
        # correctly as a string below INV-9999.
        used = [n for n in (parse_invoice_number(x) for x in existing) if n is not None]
        if used:
            start = max(used) + 1

    connection.execute(target.insert().values(id=INVOICE_COUNTER_ID, next_value=start))
