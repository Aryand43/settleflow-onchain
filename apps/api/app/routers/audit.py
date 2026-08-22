from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.audit import InvoiceAuditEvent
from app.models.invoice import Invoice
from app.models.user import User

router = APIRouter(prefix="/invoices")


class AuditEventResponse(BaseModel):
    id: int
    event_type: str
    source: str
    event_data: Optional[dict[str, Any]] = None
    evidence: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceAuditResponse(BaseModel):
    invoice_id: int
    events: list[AuditEventResponse]


def _owned_invoice_id(db: Session, invoice_id: int, user: User) -> int:
    invoice = (
        db.query(Invoice.id)
        .filter(Invoice.id == invoice_id, Invoice.owner_id == user.id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice_id


@router.get("/{invoice_id}/audit", response_model=InvoiceAuditResponse)
def get_invoice_audit(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _owned_invoice_id(db, invoice_id, user)
    rows = (
        db.query(InvoiceAuditEvent)
        .filter(InvoiceAuditEvent.invoice_id == invoice_id)
        .order_by(InvoiceAuditEvent.created_at.asc(), InvoiceAuditEvent.id.asc())
        .all()
    )
    return InvoiceAuditResponse(invoice_id=invoice_id, events=rows)
