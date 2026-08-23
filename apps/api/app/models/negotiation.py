from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MessageSender(str, enum.Enum):
    customer = "customer"
    agent = "agent"


class NegotiationMessage(Base):
    __tablename__ = "negotiation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    sender: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    invoice = relationship("Invoice", back_populates="negotiation_messages")


class ExtensionRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    denied = "denied"


class ExtensionRequest(Base):
    """A due-date extension the agent would not grant on its own.

    Anything past the agent's auto-grant cap lands here as `pending` and stays
    inert until the merchant approves or denies it — the due date is only
    touched on approval, never at request time."""

    __tablename__ = "extension_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    requested_days: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=ExtensionRequestStatus.pending.value, nullable=False, index=True
    )
    # Set only when the merchant approves, so an approved row records what was
    # actually applied rather than what was asked for.
    granted_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    new_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    invoice = relationship("Invoice", back_populates="extension_requests")
