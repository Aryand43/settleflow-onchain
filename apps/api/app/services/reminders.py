from datetime import date

from sqlalchemy.orm import Session

from app.models.activity import ActivityEvent, EventType
from app.models.invoice import Invoice, InvoiceStatus
from app.services.email import get_email_service
from app.services.invoice import log_activity


def _reminder_tier(days_overdue: int) -> str:
    """Maps how overdue an invoice is to a reminder tone. Tiers only ever
    escalate — an invoice never drops back to a gentler tier as it ages."""
    if days_overdue >= 7:
        return "final"
    if days_overdue >= 3:
        return "firm"
    return "friendly"


def _reminder_already_sent(db: Session, invoice_id: int, rule: str) -> bool:
    events = (
        db.query(ActivityEvent)
        .filter_by(invoice_id=invoice_id, event_type=EventType.reminder_sent.value)
        .all()
    )
    return any(e.metadata_json and e.metadata_json.get("rule") == rule for e in events)


def send_reminder(db: Session, invoice: Invoice, rule: str = "manual") -> Invoice:
    if invoice.status == InvoiceStatus.paid.value:
        return invoice

    if _reminder_already_sent(db, invoice.id, rule):
        return invoice

    days_overdue = max(0, (date.today() - invoice.due_date).days)
    tier = _reminder_tier(days_overdue)
    email_service = get_email_service()
    result = email_service.send_reminder_email(
        to_email=invoice.customer.email,
        customer_name=invoice.customer.name,
        invoice_number=invoice.invoice_number,
        amount=invoice.amount,
        currency=invoice.currency,
        days_overdue=days_overdue or 1,
        payment_url=invoice.payment_url or "",
        tier=tier,
    )

    invoice.reminder_count += 1
    db.commit()
    db.refresh(invoice)

    # The timeline says what actually happened. "Sent" only appears when a mail
    # server accepted the message; otherwise it reads as drafted, and a delivery
    # failure is recorded rather than swallowed.
    if result.delivered:
        outcome = f"sent to {result.to_email}"
    elif result.error:
        outcome = f"FAILED to send to {result.to_email}"
    else:
        outcome = "drafted"

    metadata = {"rule": rule, "tier": tier, **result.as_metadata()}
    log_activity(
        db,
        invoice_id=invoice.id,
        event_type=EventType.reminder_sent.value,
        message=(
            f"{tier.capitalize()} reminder {outcome} for {invoice.invoice_number} "
            f"({days_overdue}d overdue)"
        ),
        metadata=metadata,
    )
    return invoice


def process_overdue_after_simulate(db: Session, invoice: Invoice) -> None:
    if invoice.status != InvoiceStatus.overdue.value:
        return
    send_reminder(db, invoice, rule="overdue_simulated")


def run_collections_agent(db: Session, owner_id: int) -> dict:
    """The auto-chasing agent: reviews this freelancer's overdue invoices and
    sends the next-tier reminder for any that haven't received one yet at their
    current tier. In production this is what a scheduled job calls periodically;
    the demo triggers it on click instead of waiting on a scheduler, same as the
    existing simulate-* affordances.

    The agent only ever drafts and sends reminder emails — it has no path to
    mark an invoice paid or move funds, same boundary as the parser."""
    overdue_invoices = (
        db.query(Invoice)
        .filter(Invoice.owner_id == owner_id, Invoice.status == InvoiceStatus.overdue.value)
        .all()
    )

    reviewed = 0
    sent = []
    for invoice in overdue_invoices:
        reviewed += 1
        days_overdue = max(0, (date.today() - invoice.due_date).days)
        tier = _reminder_tier(days_overdue)
        rule = f"agent_{tier}"

        if _reminder_already_sent(db, invoice.id, rule):
            continue

        send_reminder(db, invoice, rule=rule)
        delivery = (
            db.query(ActivityEvent)
            .filter_by(invoice_id=invoice.id, event_type=EventType.reminder_sent.value)
            .order_by(ActivityEvent.created_at.desc())
            .first()
        )
        sent.append(
            {
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "tier": tier,
                "days_overdue": days_overdue,
                "to": invoice.customer.email,
                "delivered": bool(delivery and (delivery.metadata_json or {}).get("delivered")),
            }
        )

    return {"invoices_reviewed": reviewed, "reminders_sent": sent}
