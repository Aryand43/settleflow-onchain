from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import verify_api_key
from app.models.activity import ActivityEvent
from app.models.invoice import Invoice, InvoiceStatus
from app.models.negotiation import NegotiationMessage
from app.repositories.customer import get_customer_repository
from app.schemas import (
    DashboardSummary,
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


@router.get("", response_model=list[InvoiceResponse], dependencies=[Depends(verify_api_key)])
def list_invoices(db: Session = Depends(get_db)):
    invoices = db.query(Invoice).options(joinedload(Invoice.customer)).order_by(Invoice.created_at.desc()).all()
    return [invoice_to_response(inv) for inv in invoices]


@router.post("/parse-command", response_model=ParsedCommand, dependencies=[Depends(verify_api_key)])
async def parse_invoice_command(body: ParseCommandRequest):
    return await parse_command(body.command)


@router.post("", response_model=InvoiceResponse, status_code=201, dependencies=[Depends(verify_api_key)])
def create_invoice_endpoint(data: InvoiceCreate, db: Session = Depends(get_db)):
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    customer = get_customer_repository().list_customers(db)
    if not any(c.id == data.customer_id for c in customer):
        raise HTTPException(status_code=404, detail="Customer not found")
    invoice = create_invoice(db, data)
    db.refresh(invoice)
    invoice = db.query(Invoice).options(joinedload(Invoice.customer)).filter(Invoice.id == invoice.id).one()
    return invoice_to_response(invoice)


@router.get("/by-token/{payment_token}/payment-page", response_model=PaymentPageResponse)
def payment_page_by_token(payment_token: str, db: Session = Depends(get_db)):
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer))
        .filter(Invoice.payment_token == payment_token)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    settings = get_settings()
    return PaymentPageResponse(
        merchant_name=settings.merchant_name,
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


@router.get("/{invoice_id}", response_model=InvoiceResponse, dependencies=[Depends(verify_api_key)])
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer))
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice_to_response(invoice)


@router.get("/{invoice_id}/payment-page", response_model=PaymentPageResponse)
def payment_page(invoice_id: int, db: Session = Depends(get_db)):
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer))
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    settings = get_settings()
    return PaymentPageResponse(
        merchant_name=settings.merchant_name,
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


@router.post("/{invoice_id}/send", dependencies=[Depends(verify_api_key)])
def send_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer))
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    settings = get_settings()
    email_service = get_email_service()
    path = email_service.send_invoice_email(
        merchant_name=settings.merchant_name,
        customer_name=invoice.customer.name,
        invoice_number=invoice.invoice_number,
        amount=invoice.amount,
        currency=invoice.currency,
        description=invoice.description,
        due_date=str(invoice.due_date),
        payment_url=invoice.payment_url or "",
    )

    from app.services.invoice import log_activity
    from app.models.activity import EventType

    log_activity(
        db,
        invoice_id=invoice.id,
        event_type=EventType.invoice_sent.value,
        message=f"Invoice email sent for {invoice.invoice_number}",
        metadata={"email_preview": path},
    )
    return {"message": "Invoice email preview generated", "path": path}


@router.post("/{invoice_id}/simulate-payment", dependencies=[Depends(verify_api_key)])
def simulate_payment(invoice_id: int, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Simulate payment only available in DEMO_MODE")

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
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
    invoice = db.query(Invoice).options(joinedload(Invoice.customer)).filter(Invoice.id == invoice_id).one()
    return {"message": "Payment simulated", "invoice": invoice_to_response(invoice)}


@router.post("/{invoice_id}/simulate-time", dependencies=[Depends(verify_api_key)])
def simulate_time(invoice_id: int, days: int = 3, db: Session = Depends(get_db)):
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer))
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == InvoiceStatus.paid.value:
        raise HTTPException(status_code=400, detail="Cannot simulate time on paid invoice")

    mark_overdue(db, invoice, additional_days=days)
    process_overdue_after_simulate(db, invoice)
    db.refresh(invoice)
    invoice = db.query(Invoice).options(joinedload(Invoice.customer)).filter(Invoice.id == invoice_id).one()
    return {"message": "Time simulated — invoice overdue", "invoice": invoice_to_response(invoice)}


@router.post("/{invoice_id}/send-reminder", dependencies=[Depends(verify_api_key)])
def send_reminder_endpoint(invoice_id: int, db: Session = Depends(get_db)):
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer))
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    send_reminder(db, invoice, rule="manual")
    db.refresh(invoice)
    invoice = db.query(Invoice).options(joinedload(Invoice.customer)).filter(Invoice.id == invoice_id).one()
    return {"message": "Reminder sent", "invoice": invoice_to_response(invoice)}


@router.get(
    "/{invoice_id}/messages",
    response_model=list[NegotiationMessageResponse],
    dependencies=[Depends(verify_api_key)],
)
def invoice_messages(invoice_id: int, db: Session = Depends(get_db)):
    return (
        db.query(NegotiationMessage)
        .filter(NegotiationMessage.invoice_id == invoice_id)
        .order_by(NegotiationMessage.created_at)
        .all()
    )


@router.get("/{invoice_id}/activity", dependencies=[Depends(verify_api_key)])
def invoice_activity(invoice_id: int, db: Session = Depends(get_db)):
    events = (
        db.query(ActivityEvent)
        .filter(ActivityEvent.invoice_id == invoice_id)
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
