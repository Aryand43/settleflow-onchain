from __future__ import annotations

import re
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.activity import EventType
from app.models.invoice import Invoice, InvoiceStatus
from app.models.negotiation import MessageSender, NegotiationMessage
from app.services.invoice import log_activity

MAX_AUTO_EXTENSION_DAYS = 7
DEFAULT_EXTENSION_DAYS = 5

EXTENSION_PATTERN = re.compile(r"(\d+)\s*(?:more\s*)?days?", re.IGNORECASE)
EXTENSION_KEYWORDS = ("more time", "extend", "extension", "delay", "later", "push back")
INSTALLMENT_KEYWORDS = ("installment", "instalment", "partial", "split", "half now", "payment plan")


def _classify_intent(message: str) -> str:
    text = message.lower()
    if any(k in text for k in INSTALLMENT_KEYWORDS):
        return "installment"
    if any(k in text for k in EXTENSION_KEYWORDS) or EXTENSION_PATTERN.search(text):
        return "extension"
    return "generic"


def _save(db: Session, invoice_id: int, sender: str, message: str) -> NegotiationMessage:
    entry = NegotiationMessage(invoice_id=invoice_id, sender=sender, message=message)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def handle_customer_message(db: Session, invoice: Invoice, message: str) -> dict:
    """Lets a customer ask for more time or a payment plan, and has the agent
    respond within a hard boundary: it can push a due date back by a small,
    capped amount, and it can draft replies — it can never waive an amount,
    change the on-chain payment amount, or mark an invoice paid. Anything
    outside the auto-grantable range is drafted as "forwarded to the
    merchant," not silently approved."""
    _save(db, invoice.id, MessageSender.customer.value, message)

    if invoice.status == InvoiceStatus.paid.value:
        reply = "This invoice is already settled — there's nothing outstanding to adjust."
        _save(db, invoice.id, MessageSender.agent.value, reply)
        return {"intent": "generic", "auto_granted": False, "reply": reply}

    intent = _classify_intent(message)

    if intent == "extension":
        match = EXTENSION_PATTERN.search(message)
        requested_days = int(match.group(1)) if match else DEFAULT_EXTENSION_DAYS

        if requested_days <= MAX_AUTO_EXTENSION_DAYS:
            invoice.due_date = invoice.due_date + timedelta(days=requested_days)
            if invoice.status == InvoiceStatus.overdue.value:
                invoice.status = InvoiceStatus.pending.value
            db.commit()
            db.refresh(invoice)

            reply = (
                f"No problem — I've pushed the due date to {invoice.due_date.isoformat()} "
                f"({requested_days} extra day(s)). No further action needed."
            )
            log_activity(
                db,
                invoice_id=invoice.id,
                event_type=EventType.due_date_extended.value,
                message=f"Agent auto-granted a {requested_days}-day extension for {invoice.invoice_number}",
                metadata={"requested_days": requested_days, "new_due_date": invoice.due_date.isoformat()},
            )
            _save(db, invoice.id, MessageSender.agent.value, reply)
            return {"intent": intent, "auto_granted": True, "reply": reply}

        reply = (
            f"That's a bigger extension than I can approve on my own ({requested_days} days). "
            "I've flagged this for the merchant to review directly — nothing's changed yet."
        )
        _save(db, invoice.id, MessageSender.agent.value, reply)
        return {"intent": intent, "auto_granted": False, "reply": reply}

    if intent == "installment":
        reply = (
            "This payment link only supports paying the full amount in one transaction right now, "
            "so I can't split it up myself. I've shared your request with the merchant to arrange "
            "directly."
        )
        _save(db, invoice.id, MessageSender.agent.value, reply)
        return {"intent": intent, "auto_granted": False, "reply": reply}

    reply = "Thanks for the note — I've shared it with the merchant."
    _save(db, invoice.id, MessageSender.agent.value, reply)
    return {"intent": intent, "auto_granted": False, "reply": reply}
