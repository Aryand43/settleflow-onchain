from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models.activity import ActivityEvent
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.negotiation import NegotiationMessage
from app.models.user import User
from app.schemas import (
    InvoiceCreate,
    InvoiceResponse,
    NegotiationMessageCreate,
    NegotiationMessageResponse,
    ParseCommandRequest,
    ParsedCommand,
    PaymentPageResponse,
)
from app.services.blockchain import chain_ready, pay_invoice_onchain, scan_blockchain_events
from app.services.email import get_email_service
from app.services.invoice import create_invoice, invoice_to_response, mark_overdue, mark_paid
from app.services.negotiation import handle_customer_message
from app.services.parser import parse_command
from app.services.reminders import process_overdue_after_simulate, send_reminder

router = APIRouter(prefix="/invoices")


def _owned_invoice(db: Session, invoice_id: int, user: User) -> Invoice:
    """Loads an invoice the signed-in freelancer actually owns.

    Someone else's invoice id returns 404 rather than 403 — a 403 would confirm
    the invoice exists, which is itself a leak across accounts."""
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer))
        .filter(Invoice.id == invoice_id, Invoice.owner_id == user.id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


def _payment_page(invoice: Invoice) -> PaymentPageResponse:
    settings = get_settings()
    return PaymentPageResponse(
        # The freelancer's own name, not a global setting — the customer should
        # see who is actually billing them.
        merchant_name=invoice.owner.display_name if invoice.owner else settings.merchant_name,
        invoice_number=invoice.invoice_number,
        description=invoice.description,
        amount=invoice.amount,
        currency=invoice.currency,
        due_date=invoice.due_date,
        status=invoice.status,
        customer_name=invoice.customer.name,
        payment_url=invoice.payment_url or "",
        payment_token=invoice.payment_token,
        on_chain_invoice_id=invoice.on_chain_invoice_id,
        demo_mode=settings.demo_mode,
        chain_configured=bool(settings.rpc_url and settings.payment_contract_address),
    )


@router.get("", response_model=list[InvoiceResponse])
def list_invoices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer))
        .filter(Invoice.owner_id == user.id)
        .order_by(Invoice.created_at.desc())
        .all()
    )
    return [invoice_to_response(inv) for inv in invoices]


@router.post("/parse-command", response_model=ParsedCommand)
async def parse_invoice_command(
    body: ParseCommandRequest, user: User = Depends(get_current_user)
):
    return await parse_command(body.command)


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice_endpoint(
    data: InvoiceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    customer = (
        db.query(Customer)
        .filter(Customer.id == data.customer_id, Customer.owner_id == user.id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    invoice = create_invoice(db, data, user)
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer))
        .filter(Invoice.id == invoice.id)
        .one()
    )
    return invoice_to_response(invoice)


# --- Public payer surface: no auth, addressed only by an unguessable token ---


@router.get("/by-token/{payment_token}/payment-page", response_model=PaymentPageResponse)
def payment_page_by_token(payment_token: str, db: Session = Depends(get_db)):
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer), joinedload(Invoice.owner))
        .filter(Invoice.payment_token == payment_token)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _payment_page(invoice)


@router.get("/by-token/{payment_token}/messages", response_model=list[NegotiationMessageResponse])
def payment_page_messages(payment_token: str, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.payment_token == payment_token).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return (
        db.query(NegotiationMessage)
        .filter(NegotiationMessage.invoice_id == invoice.id)
        .order_by(NegotiationMessage.created_at)
        .all()
    )


@router.post("/by-token/{payment_token}/messages")
def send_payment_page_message(
    payment_token: str, body: NegotiationMessageCreate, db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(Invoice.payment_token == payment_token).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return handle_customer_message(db, invoice, body.message.strip())


# --- Merchant surface: everything below is scoped to the signed-in account ---


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return invoice_to_response(_owned_invoice(db, invoice_id, user))


@router.get("/{invoice_id}/payment-page", response_model=PaymentPageResponse)
def payment_page(
    invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return _payment_page(_owned_invoice(db, invoice_id, user))


@router.post("/{invoice_id}/send")
def send_invoice(
    invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    from app.models.activity import EventType
    from app.services.invoice import log_activity

    invoice = _owned_invoice(db, invoice_id, user)
    email_service = get_email_service()
    result = email_service.send_invoice_email(
        merchant_name=user.display_name,
        to_email=invoice.customer.email,
        customer_name=invoice.customer.name,
        invoice_number=invoice.invoice_number,
        amount=invoice.amount,
        currency=invoice.currency,
        description=invoice.description,
        due_date=str(invoice.due_date),
        payment_url=invoice.payment_url or "",
    )

    log_activity(
        db,
        invoice_id=invoice.id,
        event_type=EventType.invoice_sent.value,
        message=f"Invoice email {'sent to ' + invoice.customer.email if result.delivered else 'drafted'} for {invoice.invoice_number}",
        metadata=result.as_metadata(),
    )
    if result.delivered:
        message = f"Invoice email sent to {invoice.customer.email}"
    elif result.error:
        message = f"Could not send to {invoice.customer.email} — {result.error}"
    else:
        message = (
            "Invoice written to email_previews/ — SMTP is not configured, so nothing was sent"
        )

    return {
        "message": message,
        "delivered": result.delivered,
        "path": result.preview_path,
    }


@router.post("/{invoice_id}/simulate-payment")
def simulate_payment(
    invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Simulate payment only available in DEMO_MODE")

    invoice = _owned_invoice(db, invoice_id, user)
    if invoice.status == InvoiceStatus.paid.value:
        return {"message": "Already paid", "invoice": invoice_to_response(invoice)}

    if chain_ready(settings) and settings.demo_payer_private_key and invoice.on_chain_invoice_id:
        # Real chain configured (Anvil devnet by default): pay for real and let
        # the scan pick up the InvoicePaid event, same as production would.
        pay_invoice_onchain(invoice)
        scan_blockchain_events(db)
    else:
        fake_hash = f"0x{'a' * 64}"
        mark_paid(db, invoice, fake_hash, simulated=True)

    db.refresh(invoice)
    return {"message": "Payment simulated", "invoice": invoice_to_response(invoice)}


@router.post("/{invoice_id}/simulate-time")
def simulate_time(
    invoice_id: int,
    days: int = 3,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invoice = _owned_invoice(db, invoice_id, user)
    if invoice.status == InvoiceStatus.paid.value:
        raise HTTPException(status_code=400, detail="Cannot simulate time on paid invoice")

    mark_overdue(db, invoice, additional_days=days)
    process_overdue_after_simulate(db, invoice)
    db.refresh(invoice)
    return {"message": "Time simulated — invoice overdue", "invoice": invoice_to_response(invoice)}


@router.post("/{invoice_id}/send-reminder")
def send_reminder_endpoint(
    invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    from app.models.activity import EventType
    from app.services.email import email_delivery_configured

    invoice = _owned_invoice(db, invoice_id, user)
    send_reminder(db, invoice, rule="manual")
    db.refresh(invoice)

    latest = (
        db.query(ActivityEvent)
        .filter_by(invoice_id=invoice.id, event_type=EventType.reminder_sent.value)
        .order_by(ActivityEvent.created_at.desc())
        .first()
    )
    delivered = bool(latest and (latest.metadata_json or {}).get("delivered"))
    error = (latest.metadata_json or {}).get("error") if latest else None

    if delivered:
        message = f"Reminder sent to {invoice.customer.email}"
    elif error:
        message = f"Could not send to {invoice.customer.email} — {error}"
    elif not email_delivery_configured():
        message = "Reminder written to email_previews/ — SMTP is not configured, so nothing was sent"
    else:
        message = "Reminder drafted"

    return {
        "message": message,
        "delivered": delivered,
        "invoice": invoice_to_response(invoice),
    }


@router.get("/{invoice_id}/messages", response_model=list[NegotiationMessageResponse])
def invoice_messages(
    invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    invoice = _owned_invoice(db, invoice_id, user)
    return (
        db.query(NegotiationMessage)
        .filter(NegotiationMessage.invoice_id == invoice.id)
        .order_by(NegotiationMessage.created_at)
        .all()
    )


@router.get("/{invoice_id}/activity")
def invoice_activity(
    invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    invoice = _owned_invoice(db, invoice_id, user)
    events = (
        db.query(ActivityEvent)
        .filter(ActivityEvent.invoice_id == invoice.id)
        .order_by(ActivityEvent.created_at.desc())
        .all()
    )
    return [
        {
            "id": e.id,
            "invoice_id": e.invoice_id,
            "event_type": e.event_type,
            "message": e.message,
            "metadata": e.metadata_json,
            "created_at": e.created_at,
        }
        for e in events
    ]
