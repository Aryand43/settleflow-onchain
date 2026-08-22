from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models.activity import ActivityEvent, EventType
from app.models.invoice import Invoice, InvoiceStatus
from app.services.audit_service import log_invoice_event
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


def send_reminder(
    db: Session,
    invoice: Invoice,
    rule: str = "manual",
    email_service=None,
    skip_duplicate_check: bool = False,
):
    """Sends one reminder and records what actually happened.

    Returns the EmailResult, or None when nothing was sent — the collections
    agent needs the delivery outcome and used to re-query the activity table
    for it, which over a network-attached database meant an extra round trip
    per invoice.

    `email_service` lets a caller pass a service with an open SMTP connection
    so a batch doesn't re-authenticate per message."""
    if invoice.status == InvoiceStatus.paid.value:
        return None

    if not skip_duplicate_check and _reminder_already_sent(db, invoice.id, rule):
        return None

    days_overdue = max(0, (date.today() - invoice.due_date).days)
    tier = _reminder_tier(days_overdue)
    email_service = email_service or get_email_service()
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
        commit=False,
    )
    # One commit covers the counter bump and the timeline row together.
    db.commit()
    log_invoice_event(
        db,
        invoice.id,
        "reminder_generated",
        "system",
        event_data={
            "rule": rule,
            "tier": tier,
            "reminder_count": invoice.reminder_count,
            "delivered": result.delivered,
        },
        evidence={"email_preview": result.preview_path} if result.preview_path else None,
    )
    return result


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
        .options(joinedload(Invoice.customer))
        .filter(Invoice.owner_id == owner_id, Invoice.status == InvoiceStatus.overdue.value)
        .all()
    )
    if not overdue_invoices:
        return {"invoices_reviewed": 0, "reminders_sent": []}

    # Every rule already used, fetched once. This was a query per invoice, run
    # twice over (here and again inside send_reminder) — six round trips per
    # invoice to a database in another region.
    invoice_ids = [inv.id for inv in overdue_invoices]
    already_sent: set[tuple[int, str]] = set()
    for event in (
        db.query(ActivityEvent)
        .filter(
            ActivityEvent.invoice_id.in_(invoice_ids),
            ActivityEvent.event_type == EventType.reminder_sent.value,
        )
        .all()
    ):
        rule_used = (event.metadata_json or {}).get("rule")
        if rule_used:
            already_sent.add((event.invoice_id, rule_used))

    due = []
    for invoice in overdue_invoices:
        days_overdue = max(0, (date.today() - invoice.due_date).days)
        tier = _reminder_tier(days_overdue)
        rule = f"agent_{tier}"
        if (invoice.id, rule) not in already_sent:
            due.append((invoice, days_overdue, tier, rule))

    sent = []
    if due:
        # One SMTP login for the whole batch instead of one per reminder.
        with get_email_service().session() as mailer:
            for invoice, days_overdue, tier, rule in due:
                result = send_reminder(
                    db,
                    invoice,
                    rule=rule,
                    email_service=mailer,
                    skip_duplicate_check=True,
                )
                sent.append(
                    {
                        "invoice_id": invoice.id,
                        "invoice_number": invoice.invoice_number,
                        "tier": tier,
                        "days_overdue": days_overdue,
                        "to": invoice.customer.email,
                        "delivered": bool(result and result.delivered),
                    }
                )

    return {"invoices_reviewed": len(overdue_invoices), "reminders_sent": sent}
