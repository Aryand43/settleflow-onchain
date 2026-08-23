from __future__ import annotations

import enum
import hashlib
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

INVOICE_NUMBER_PREFIX = "INV-"


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

    # Invoice numbers restart at INV-0001 for every freelancer, so the
    # uniqueness that matters is per owner, not global.
    __table_args__ = (UniqueConstraint("owner_id", "invoice_number", name="uq_invoice_owner_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
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

    owner = relationship("User", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")
    activity_events = relationship("ActivityEvent", back_populates="invoice")
    audit_events = relationship("InvoiceAuditEvent", back_populates="invoice")
    negotiation_messages = relationship(
        "NegotiationMessage", back_populates="invoice", order_by="NegotiationMessage.created_at"
    )
    extension_requests = relationship(
        "ExtensionRequest", back_populates="invoice", order_by="ExtensionRequest.created_at"
    )


class InvoiceCounter(Base):
    """Hands out the sequential part of INV-0001 — one row per freelancer, so
    everyone's invoices start at 1 and nobody can infer how much business
    anyone else is doing from their invoice numbers.

    Incremented under a row lock, so two concurrent creations can't be handed
    the same number — which would also mean two identical
    `on_chain_invoice_id`s, and the router rejects a duplicate invoice id."""

    __tablename__ = "invoice_counters"

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


def parse_invoice_number(invoice_number: str) -> int | None:
    """`INV-0007` -> 7. Returns None for anything not in that shape."""
    if not invoice_number or not invoice_number.startswith(INVOICE_NUMBER_PREFIX):
        return None
    suffix = invoice_number[len(INVOICE_NUMBER_PREFIX) :]
    return int(suffix) if suffix.isdigit() else None


def format_invoice_number(value: int) -> str:
    return f"{INVOICE_NUMBER_PREFIX}{value:04d}"


def on_chain_invoice_id(owner_id: int, invoice_number: str) -> str:
    """Derives the `bytes32` the router keys a payment request by.

    Salted with the owner: invoice numbers restart per freelancer, so hashing
    the number alone would give every freelancer's INV-0001 the same on-chain
    id, and `createPaymentRequest` reverts on a duplicate."""
    return "0x" + hashlib.sha256(f"{owner_id}:{invoice_number}".encode()).hexdigest()
