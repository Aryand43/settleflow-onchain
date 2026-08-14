from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.activity import ActivityEvent, EventType
from app.models.invoice import (
    INVOICE_COUNTER_ID,
    Invoice,
    InvoiceCounter,
    InvoiceStatus,
    format_invoice_number,
    parse_invoice_number,
)
from app.schemas import InvoiceCreate, InvoiceResponse


USDC_DECIMALS = 6


def _next_invoice_number(db: Session) -> str:
    """Claims the next number by incrementing the counter row under a row lock,
    held until the caller commits.

    The old `count() + 1` reread the table with no lock, so two concurrent
    creates both saw the same count and produced the same INV-xxxx — one of
    them dying on the unique constraint, and worse, both deriving the same
    `on_chain_invoice_id`. Deleting an invoice also made it hand out a number
    that was already taken.

    FOR UPDATE is a no-op on SQLite, which has no row locks; its single-writer
    model covers the same ground for the demo, and the unique constraint is
    still the backstop."""
    counter = (
        db.query(InvoiceCounter)
        .filter(InvoiceCounter.id == INVOICE_COUNTER_ID)
        .with_for_update()
        .one_or_none()
    )

    if counter is None:
        # The row is normally created with the table (see the after_create hook
        # in models.invoice). This covers a database whose counter row was
        # removed by hand.
        counter = InvoiceCounter(id=INVOICE_COUNTER_ID, next_value=_highest_invoice_number(db) + 1)
        db.add(counter)
        db.flush()

    value = counter.next_value
    counter.next_value = value + 1
    db.flush()
    return format_invoice_number(value)


def _highest_invoice_number(db: Session) -> int:
    numbers = [
        parsed
        for parsed in (parse_invoice_number(n) for (n,) in db.query(Invoice.invoice_number).all())
        if parsed is not None
    ]
    return max(numbers) if numbers else 0


def sync_invoice_counter(db: Session) -> int:
    """Points the counter just past the highest invoice number present.

    Needed after inserting invoices with hand-written numbers (scripts/seed.py
    does exactly that), which otherwise leaves the counter pointing at numbers
    already on disk. Returns the value the next invoice will use."""
    next_value = _highest_invoice_number(db) + 1
    counter = db.query(InvoiceCounter).filter(InvoiceCounter.id == INVOICE_COUNTER_ID).one_or_none()
    if counter is None:
        counter = InvoiceCounter(id=INVOICE_COUNTER_ID, next_value=next_value)
        db.add(counter)
    else:
        counter.next_value = max(counter.next_value, next_value)
    db.commit()
    return counter.next_value


def _to_base_units(amount: float) -> int:
    return int(round(amount * (10**USDC_DECIMALS)))


def _on_chain_id(invoice_number: str) -> str:
    return "0x" + hashlib.sha256(invoice_number.encode()).hexdigest()


def invoice_to_response(invoice: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        customer_id=invoice.customer_id,
        customer_name=invoice.customer.name if invoice.customer else None,
        merchant_wallet=invoice.merchant_wallet,
        amount=invoice.amount,
        currency=invoice.currency,
        amount_wei_or_base_units=invoice.amount_wei_or_base_units,
        description=invoice.description,
        due_date=invoice.due_date,
        status=invoice.status,
        payment_url=invoice.payment_url,
        payment_token=invoice.payment_token,
        blockchain_tx_hash=invoice.blockchain_tx_hash,
        on_chain_invoice_id=invoice.on_chain_invoice_id,
        created_at=invoice.created_at,
        paid_at=invoice.paid_at,
        reminder_count=invoice.reminder_count,
    )


def log_activity(
    db: Session,
    *,
    invoice_id: Optional[int],
    event_type: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> ActivityEvent:
    event = ActivityEvent(
        invoice_id=invoice_id,
        event_type=event_type,
        message=message,
        metadata_json=metadata,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_invoice(db: Session, data: InvoiceCreate) -> Invoice:
    settings = get_settings()
    invoice_number = _next_invoice_number(db)
    payment_token = str(uuid.uuid4())
    payment_url = f"{settings.web_base_url}/pay/{payment_token}"

    invoice = Invoice(
        invoice_number=invoice_number,
        customer_id=data.customer_id,
        merchant_wallet=settings.merchant_wallet,
        amount=data.amount,
        currency=data.currency.upper(),
        amount_wei_or_base_units=_to_base_units(data.amount),
        description=data.description,
        due_date=data.due_date,
        status=InvoiceStatus.pending.value,
        payment_url=payment_url,
        payment_token=payment_token,
        on_chain_invoice_id=_on_chain_id(invoice_number),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    log_activity(
        db,
        invoice_id=invoice.id,
        event_type=EventType.invoice_created.value,
        message=f"Invoice {invoice_number} created for {data.amount} {data.currency.upper()}",
        metadata={"invoice_number": invoice_number},
    )

    from app.services.blockchain import chain_ready, register_payment_request

    if chain_ready(settings):
        try:
            register_payment_request(invoice)
        except Exception as exc:
            log_activity(
                db,
                invoice_id=invoice.id,
                event_type=EventType.payment_failed.value,
                message=f"On-chain registration failed for {invoice_number}: {exc}",
            )

    return invoice


def mark_paid(db: Session, invoice: Invoice, tx_hash: str, simulated: bool = False) -> Invoice:
    if invoice.status == InvoiceStatus.paid.value and invoice.blockchain_tx_hash:
        return invoice

    invoice.status = InvoiceStatus.paid.value
    invoice.blockchain_tx_hash = tx_hash
    invoice.paid_at = datetime.utcnow()
    db.commit()
    db.refresh(invoice)

    log_activity(
        db,
        invoice_id=invoice.id,
        event_type=EventType.payment_detected.value,
        message=f"Payment detected for {invoice.invoice_number}",
        metadata={"tx_hash": tx_hash, "simulated": simulated},
    )
    log_activity(
        db,
        invoice_id=invoice.id,
        event_type=EventType.payment_confirmed.value,
        message=f"Payment confirmed for {invoice.invoice_number}",
        metadata={"tx_hash": tx_hash},
    )
    return invoice


def mark_overdue(db: Session, invoice: Invoice, additional_days: int = 1) -> Invoice:
    was_already_overdue = invoice.status == InvoiceStatus.overdue.value

    if was_already_overdue:
        # Already overdue: push further into the past so the demo can walk
        # through the collections agent's escalation tiers on repeat clicks.
        invoice.due_date = invoice.due_date - timedelta(days=additional_days)
    else:
        invoice.status = InvoiceStatus.overdue.value
        invoice.due_date = date.today() - timedelta(days=1)

    db.commit()
    db.refresh(invoice)

    if not was_already_overdue:
        log_activity(
            db,
            invoice_id=invoice.id,
            event_type=EventType.invoice_overdue.value,
            message=f"Invoice {invoice.invoice_number} marked overdue",
        )
    return invoice
