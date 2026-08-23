from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditEventType(str, enum.Enum):
    invoice_created = "invoice_created"
    invoice_parsed = "invoice_parsed"
    invoice_confirmed = "invoice_confirmed"
    payment_page_opened = "payment_page_opened"
    payment_submitted = "payment_submitted"
    payment_detected = "payment_detected"
    invoice_marked_paid = "invoice_marked_paid"
    invoice_sent = "invoice_sent"
    invoice_overdue = "invoice_overdue"
    reminder_generated = "reminder_generated"
    negotiation_message = "negotiation_message"
    ai_query = "ai_query"
    extension_auto_granted = "extension_auto_granted"
    extension_requested = "extension_requested"
    extension_approved = "extension_approved"
    extension_denied = "extension_denied"


class AuditSource(str, enum.Enum):
    user = "user"
    system = "system"
    blockchain = "blockchain"
    ai = "ai"


class InvoiceAuditEvent(Base):
    """Append-only record of a meaningful invoice state change.

    Application code inserts rows through `log_invoice_event` and never
    updates or deletes them. Invoice payment status is still decided by
    existing `mark_paid` / chain-scan logic, not by this table.
    """

    __tablename__ = "invoice_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    invoice = relationship("Invoice", back_populates="audit_events")
