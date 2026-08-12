from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


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
    amount_wei_or_base_units: Mapped[int] = mapped_column(Integer, nullable=False)
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
