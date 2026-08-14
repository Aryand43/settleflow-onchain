from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.activity import ActivityEvent
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.schemas import ActivityEventResponse, DashboardSummary

router = APIRouter()


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invoices = db.query(Invoice).filter(Invoice.owner_id == user.id).all()
    paid = [i for i in invoices if i.status == InvoiceStatus.paid.value]
    pending = [i for i in invoices if i.status == InvoiceStatus.pending.value]
    overdue = [i for i in invoices if i.status == InvoiceStatus.overdue.value]

    total_collected = sum(i.amount for i in paid)
    total_outstanding = sum(i.amount for i in pending)
    total_overdue = sum(i.amount for i in overdue)
    total = total_collected + total_outstanding + total_overdue
    collection_rate = (total_collected / total * 100) if total else 0.0

    chart_data = [
        {"name": "Collected", "value": total_collected},
        {"name": "Outstanding", "value": total_outstanding},
        {"name": "Overdue", "value": total_overdue},
    ]

    return DashboardSummary(
        total_collected=total_collected,
        total_outstanding=total_outstanding,
        total_overdue=total_overdue,
        paid_count=len(paid),
        pending_count=len(pending),
        overdue_count=len(overdue),
        collection_rate=round(collection_rate, 1),
        chart_data=chart_data,
    )


@router.get("/activity", response_model=list[ActivityEventResponse])
def list_activity(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Joined through invoices rather than filtered directly: activity events
    # carry no owner of their own, and the invoice they hang off is what
    # decides who may read them.
    events = (
        db.query(ActivityEvent)
        .join(Invoice, ActivityEvent.invoice_id == Invoice.id)
        .filter(Invoice.owner_id == user.id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        ActivityEventResponse(
            id=e.id,
            invoice_id=e.invoice_id,
            event_type=e.event_type,
            message=e.message,
            metadata=e.metadata_json,
            created_at=e.created_at,
        )
        for e in events
    ]
