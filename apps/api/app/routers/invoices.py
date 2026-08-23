from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models.activity import ActivityEvent
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.negotiation import ExtensionRequest, ExtensionRequestStatus, NegotiationMessage
from app.models.user import User
from app.schemas import (
    ExtensionDecision,
    ExtensionRequestResponse,
    InvoiceCreate,
    InvoiceResponse,
    NegotiationMessageCreate,
    NegotiationMessageResponse,
    ParseCommandRequest,
    ParsedCommand,
    PaymentPageResponse,
)
from app.models.activity import EventType
from app.services.blockchain import chain_ready, pay_invoice_onchain, scan_blockchain_events
from app.services.email import get_email_service
from app.services.invoice import (
    create_invoice,
    invoice_to_response,
    log_activity,
    mark_overdue,
    mark_paid,
)
from app.services.negotiation import handle_customer_message, resolve_extension_request
from app.services.parser import parse_command
from app.services.audit_service import log_invoice_event
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


def _settle_now(db: Session, invoice: Invoice) -> None:
    """Pays an invoice the way the demo stands in for a customer's wallet.

    With a chain configured this is a genuine payment — mint, approve,
    `payInvoice` — and the status only moves once the scan sees the
    `InvoicePaid` event. Without one it falls back to a placeholder hash so the
    product is still demoable with nothing but the API running."""
    log_invoice_event(
        db,
        invoice.id,
        "payment_submitted",
        "user",
        event_data={
            "amount": invoice.amount,
            "currency": invoice.currency,
            "on_chain_invoice_id": invoice.on_chain_invoice_id,
        },
    )
    settings = get_settings()
    if chain_ready(settings) and settings.demo_payer_private_key and invoice.on_chain_invoice_id:
        try:
            pay_invoice_onchain(invoice)
        except Exception as exc:
            # A chain failure used to escape as an unhandled 500, which carries
            # no CORS headers — so the browser reported "Failed to fetch" and
            # hid the real cause. Surface it as a normal error response.
            log_activity(
                db,
                invoice_id=invoice.id,
                event_type=EventType.payment_failed.value,
                message=f"On-chain payment failed for {invoice.invoice_number}: {exc}",
            )
            raise HTTPException(
                status_code=502,
                detail=f"The payment transaction failed on-chain: {exc}. "
                "Is Anvil running and are the contracts deployed?",
            ) from exc

        # The row only moves to paid off the back of an observed InvoicePaid
        # event, so the scan is what actually settles it.
        scan_blockchain_events(db)
        db.refresh(invoice)

        if invoice.status != InvoiceStatus.paid.value:
            # The transaction went through but the row didn't move. Saying
            # "Payment complete" here is how an invoice ends up payable twice —
            # the second attempt then reverts with AlreadyPaid.
            log_activity(
                db,
                invoice_id=invoice.id,
                event_type=EventType.payment_failed.value,
                message=(
                    f"Paid on-chain but {invoice.invoice_number} did not settle — "
                    "the InvoicePaid event was not matched"
                ),
            )
            raise HTTPException(
                status_code=502,
                detail="The payment went through on-chain but this invoice didn't "
                "update. Run a blockchain scan to reconcile it.",
            )
    else:
        mark_paid(db, invoice, f"0x{'a' * 64}", simulated=True)
    db.refresh(invoice)


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
    log_invoice_event(
        db,
        invoice.id,
        "payment_page_opened",
        "user",
        event_data={"payment_token": invoice.payment_token, "status": invoice.status},
    )
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


@router.post("/by-token/{payment_token}/pay")
def pay_by_token(payment_token: str, db: Session = Depends(get_db)):
    """Lets the payer settle from their own link, which is where paying
    actually belongs — the merchant clicking 'pay' on their own dashboard was
    always a stand-in for this.

    Public on purpose: the payment token is the only credential a customer
    has, exactly like the message endpoint above. It can only ever move an
    invoice to paid, and only the one the token names."""
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo payment is only available in DEMO_MODE")

    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer), joinedload(Invoice.owner))
        .filter(Invoice.payment_token == payment_token)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status == InvoiceStatus.paid.value:
        return {"message": "Already paid", "payment_page": _payment_page(invoice)}

    if invoice.status == InvoiceStatus.cancelled.value:
        raise HTTPException(status_code=400, detail="This invoice was cancelled")

    _settle_now(db, invoice)
    return {"message": "Payment complete", "payment_page": _payment_page(invoice)}


# --- Merchant surface: everything below is scoped to the signed-in account ---


def _extension_response(request: ExtensionRequest) -> ExtensionRequestResponse:
    response = ExtensionRequestResponse.model_validate(request)
    invoice = request.invoice
    if invoice is not None:
        response.invoice_number = invoice.invoice_number
        response.customer_name = invoice.customer.name if invoice.customer else None
    return response


@router.get("/extension-requests", response_model=list[ExtensionRequestResponse])
def list_extension_requests(
    status: str = ExtensionRequestStatus.pending.value,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The merchant's approval queue: extensions the agent declined to grant
    itself, across every invoice this user owns. Defaults to the pending ones,
    since those are the only rows that need a decision."""
    query = (
        db.query(ExtensionRequest)
        .join(Invoice, ExtensionRequest.invoice_id == Invoice.id)
        .options(joinedload(ExtensionRequest.invoice).joinedload(Invoice.customer))
        .filter(Invoice.owner_id == user.id)
    )
    if status != "all":
        if status not in {s.value for s in ExtensionRequestStatus}:
            raise HTTPException(status_code=400, detail=f"Unknown status: {status}")
        query = query.filter(ExtensionRequest.status == status)

    requests = query.order_by(ExtensionRequest.created_at.desc()).all()
    return [_extension_response(r) for r in requests]


@router.post("/extension-requests/{request_id}/decision", response_model=ExtensionRequestResponse)
def decide_extension_request(
    request_id: int,
    body: ExtensionDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve or deny a pending extension. Approving is the only thing that
    moves the due date — until then the invoice is untouched."""
    request = (
        db.query(ExtensionRequest)
        .join(Invoice, ExtensionRequest.invoice_id == Invoice.id)
        .options(joinedload(ExtensionRequest.invoice).joinedload(Invoice.customer))
        .filter(ExtensionRequest.id == request_id, Invoice.owner_id == user.id)
        .first()
    )
    if not request:
        raise HTTPException(status_code=404, detail="Extension request not found")

    try:
        resolve_extension_request(db, request.invoice, request, body.approve)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _extension_response(request)


@router.get("/{invoice_id}/extension-requests", response_model=list[ExtensionRequestResponse])
def invoice_extension_requests(
    invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    invoice = _owned_invoice(db, invoice_id, user)
    requests = (
        db.query(ExtensionRequest)
        .filter(ExtensionRequest.invoice_id == invoice.id)
        .order_by(ExtensionRequest.created_at.desc())
        .all()
    )
    return [_extension_response(r) for r in requests]


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
    # Mail leaving for a customer belongs in the trail, the same as the
    # reminder emails that follow it. `delivered` distinguishes a real send
    # from a preview written to disk with SMTP unconfigured.
    log_invoice_event(
        db,
        invoice.id,
        "invoice_sent",
        "user",
        event_data={
            "to_email": invoice.customer.email,
            "delivered": result.delivered,
            "error": result.error,
        },
        evidence={"email_preview": result.preview_path} if result.preview_path else None,
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
    """Kept as a merchant-side escape hatch for when the payer window isn't
    open — the demo pays from the payment link now. Same code path."""
    settings = get_settings()
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Simulate payment only available in DEMO_MODE")

    invoice = _owned_invoice(db, invoice_id, user)
    if invoice.status == InvoiceStatus.paid.value:
        return {"message": "Already paid", "invoice": invoice_to_response(invoice)}

    _settle_now(db, invoice)
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
