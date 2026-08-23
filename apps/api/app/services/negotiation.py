from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.activity import EventType
from app.models.invoice import Invoice, InvoiceStatus
from app.models.negotiation import (
    ExtensionRequest,
    ExtensionRequestStatus,
    MessageSender,
    NegotiationMessage,
)
from app.services.audit_service import log_invoice_event
from app.services.invoice import log_activity

MAX_AUTO_EXTENSION_DAYS = 7
DEFAULT_EXTENSION_DAYS = 5

# Durations, in whatever units a customer actually writes them.
#
# This used to match `(\d+)\s*days?` only, which meant "can I get a year to
# pay?" classified as *generic* — the agent replied "I've shared it with the
# merchant" and no approval request was ever opened, so the merchant had nothing
# to approve or reject. Weeks, months and worded quantities all fell through the
# same way. Only "30 days" in digits ever reached the approval path.
UNIT_DAYS = {"day": 1, "week": 7, "fortnight": 14, "month": 30, "quarter": 90, "year": 365}

WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "couple": 2, "few": 3, "several": 3,
}

DURATION_PATTERN = re.compile(
    # `of` is optional so "a couple of months" parses like "two months".
    r"\b(\d+|" + "|".join(WORD_NUMBERS) + r")\s*(?:of\s+)?(?:more\s+|extra\s+)?"
    r"(" + "|".join(UNIT_DAYS) + r")s?\b",
    re.IGNORECASE,
)

EXTENSION_KEYWORDS = ("more time", "extend", "extension", "delay", "later", "push back")
INSTALLMENT_KEYWORDS = ("installment", "instalment", "partial", "split", "half now", "payment plan")


def requested_extension_days(message: str) -> int | None:
    """How many days the customer asked for, or None if they didn't say.

    Capped at ten years so a joke ("can I have a million years?") lands as a
    large approval request rather than an integer that overflows a date."""
    match = DURATION_PATTERN.search(message)
    if not match:
        return None
    quantity, unit = match.group(1).lower(), match.group(2).lower()
    count = int(quantity) if quantity.isdigit() else WORD_NUMBERS[quantity]
    return min(count * UNIT_DAYS[unit], 3650)


def _classify_intent(message: str) -> str:
    text = message.lower()
    if any(k in text for k in INSTALLMENT_KEYWORDS):
        return "installment"
    if any(k in text for k in EXTENSION_KEYWORDS) or DURATION_PATTERN.search(text):
        return "extension"
    return "generic"


def _save(db: Session, invoice_id: int, sender: str, message: str) -> NegotiationMessage:
    entry = NegotiationMessage(invoice_id=invoice_id, sender=sender, message=message)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _audit_reply(db: Session, invoice: Invoice, intent: str, message: str, reply: str) -> None:
    """Records an agent reply that changed nothing on the invoice.

    The extension paths write their own, more specific events; this covers the
    rest, so every customer-facing thing the agent says is in the trail rather
    than only the replies that moved a due date."""
    log_invoice_event(
        db,
        invoice_id=invoice.id,
        event_type="negotiation_message",
        source="ai",
        event_data={"intent": intent, "agent_reply": reply, "invoice_changed": False},
        evidence=message,
    )


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
        _audit_reply(db, invoice, "generic", message, reply)
        return {"intent": "generic", "auto_granted": False, "reply": reply, "pending_approval": False}

    intent = _classify_intent(message)

    if intent == "extension":
        requested_days = requested_extension_days(message) or DEFAULT_EXTENSION_DAYS

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
            # The agent moving a due date unasked is exactly what the audit
            # trail is for — record it with the customer's own words as
            # evidence, the same as the over-cap path does.
            log_invoice_event(
                db,
                invoice_id=invoice.id,
                event_type="extension_auto_granted",
                source="ai",
                event_data={
                    "requested_days": requested_days,
                    "auto_grant_cap_days": MAX_AUTO_EXTENSION_DAYS,
                    "new_due_date": invoice.due_date.isoformat(),
                },
                evidence=message,
            )
            _save(db, invoice.id, MessageSender.agent.value, reply)
            return {"intent": intent, "auto_granted": True, "reply": reply, "pending_approval": False}

        request = _open_extension_request(db, invoice, requested_days, message)

        reply = (
            f"That's a bigger extension than I can approve on my own ({requested_days} days). "
            "I've sent it to the merchant for approval — the due date stays as it is until "
            "they decide, and I'll let you know here either way."
        )
        _save(db, invoice.id, MessageSender.agent.value, reply)
        return {
            "intent": intent,
            "auto_granted": False,
            "reply": reply,
            "pending_approval": True,
            "extension_request_id": request.id,
        }

    if intent == "installment":
        reply = (
            "This payment link only supports paying the full amount in one transaction right now, "
            "so I can't split it up myself. I've shared your request with the merchant to arrange "
            "directly."
        )
        _save(db, invoice.id, MessageSender.agent.value, reply)
        _audit_reply(db, invoice, intent, message, reply)
        return {"intent": intent, "auto_granted": False, "reply": reply, "pending_approval": False}

    reply = "Thanks for the note — I've shared it with the merchant."
    _save(db, invoice.id, MessageSender.agent.value, reply)
    _audit_reply(db, invoice, intent, message, reply)
    return {"intent": intent, "auto_granted": False, "reply": reply, "pending_approval": False}


def _open_extension_request(
    db: Session, invoice: Invoice, requested_days: int, message: str
) -> ExtensionRequest:
    """Files an over-cap extension for the merchant to decide on.

    A customer who asks twice replaces their own open request rather than
    stacking a second one, so the merchant sees one decision per invoice with
    the latest number on it."""
    existing = (
        db.query(ExtensionRequest)
        .filter(
            ExtensionRequest.invoice_id == invoice.id,
            ExtensionRequest.status == ExtensionRequestStatus.pending.value,
        )
        .first()
    )
    if existing:
        existing.requested_days = requested_days
        existing.customer_message = message
        existing.created_at = datetime.utcnow()
        request = existing
    else:
        request = ExtensionRequest(
            invoice_id=invoice.id,
            requested_days=requested_days,
            customer_message=message,
        )
        db.add(request)
    db.commit()
    db.refresh(request)

    log_activity(
        db,
        invoice_id=invoice.id,
        event_type=EventType.extension_requested.value,
        message=(
            f"Customer requested a {requested_days}-day extension on {invoice.invoice_number} "
            f"— over the {MAX_AUTO_EXTENSION_DAYS}-day auto-grant cap, awaiting your approval"
        ),
        metadata={"requested_days": requested_days, "extension_request_id": request.id},
    )
    log_invoice_event(
        db,
        invoice_id=invoice.id,
        event_type="extension_requested",
        source="ai",
        event_data={
            "requested_days": requested_days,
            "auto_grant_cap_days": MAX_AUTO_EXTENSION_DAYS,
            "extension_request_id": request.id,
        },
        evidence=message,
    )
    return request


def resolve_extension_request(
    db: Session, invoice: Invoice, request: ExtensionRequest, approve: bool
) -> ExtensionRequest:
    """Applies the merchant's decision. The due date moves only here, and only
    on approval — a denied request leaves the invoice exactly as it was."""
    if request.status != ExtensionRequestStatus.pending.value:
        raise ValueError(f"Extension request is already {request.status}")

    if approve:
        invoice.due_date = invoice.due_date + timedelta(days=request.requested_days)
        if invoice.status == InvoiceStatus.overdue.value:
            invoice.status = InvoiceStatus.pending.value
        request.status = ExtensionRequestStatus.approved.value
        request.granted_days = request.requested_days
        request.new_due_date = invoice.due_date
    else:
        request.status = ExtensionRequestStatus.denied.value

    request.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(request)
    db.refresh(invoice)

    if approve:
        reply = (
            f"Good news — the merchant approved your request. The due date is now "
            f"{invoice.due_date.isoformat()} ({request.granted_days} extra day(s))."
        )
        event_type = EventType.extension_approved.value
        activity_message = (
            f"Merchant approved a {request.granted_days}-day extension on "
            f"{invoice.invoice_number} (new due date {invoice.due_date.isoformat()})"
        )
    else:
        reply = (
            "I heard back from the merchant — they weren't able to approve that extension, "
            f"so the due date stays {invoice.due_date.isoformat()}. Reply here if you'd like "
            "to work something else out."
        )
        event_type = EventType.extension_denied.value
        activity_message = (
            f"Merchant denied a {request.requested_days}-day extension request on "
            f"{invoice.invoice_number}"
        )

    log_activity(
        db,
        invoice_id=invoice.id,
        event_type=event_type,
        message=activity_message,
        metadata={
            "requested_days": request.requested_days,
            "granted_days": request.granted_days,
            "new_due_date": invoice.due_date.isoformat(),
            "extension_request_id": request.id,
        },
    )
    log_invoice_event(
        db,
        invoice_id=invoice.id,
        event_type="extension_approved" if approve else "extension_denied",
        source="user",
        event_data={
            "requested_days": request.requested_days,
            "granted_days": request.granted_days,
            "new_due_date": invoice.due_date.isoformat(),
            "extension_request_id": request.id,
        },
    )
    _save(db, invoice.id, MessageSender.agent.value, reply)
    return request
