from datetime import date

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.activity import ActivityEvent, EventType
from app.models.invoice import Invoice, InvoiceStatus
from app.services.email import get_email_service
from app.services.invoice import log_activity


def send_reminder(db: Session, invoice: Invoice, rule: str = "manual") -> Invoice:
    if invoice.status == InvoiceStatus.paid.value:
        return invoice

    existing = (
        db.query(ActivityEvent)
        .filter_by(invoice_id=invoice.id, event_type=EventType.reminder_sent.value)
        .all()
    )
    for event in existing:
        if event.metadata_json and event.metadata_json.get("rule") == rule:
            return invoice

    days_overdue = max(0, (date.today() - invoice.due_date).days)
    email_service = get_email_service()
    path = email_service.send_reminder_email(
        customer_name=invoice.customer.name,
        invoice_number=invoice.invoice_number,
        amount=invoice.amount,
        currency=invoice.currency,
        days_overdue=days_overdue or 1,
        payment_url=invoice.payment_url or "",
    )

    invoice.reminder_count += 1
    db.commit()
    db.refresh(invoice)

    log_activity(
        db,
        invoice_id=invoice.id,
        event_type=EventType.reminder_sent.value,
        message=f"Reminder sent for {invoice.invoice_number}",
        metadata={"rule": rule, "email_preview": path},
    )
    return invoice


def process_overdue_after_simulate(db: Session, invoice: Invoice) -> None:
    settings = get_settings()
    if invoice.status != InvoiceStatus.overdue.value:
        return
    send_reminder(db, invoice, rule="overdue_simulated")
