from __future__ import annotations

import json
from datetime import date
from typing import Literal

from sqlalchemy.orm import Session, joinedload

from app.models.activity import ActivityEvent
from app.models.invoice import Invoice, InvoiceStatus
from app.services.llm import chat_completions

ChatScope = Literal["payments", "overview"]

BOUNDARY = (
    "You are read-only. You cannot send email, submit a transaction, mark an "
    "invoice paid, change amounts, or run the collections agent. If the merchant "
    "asks you to do any of those, refuse and tell them to use the existing "
    "buttons on the dashboard. Paid status only comes from an observed on-chain "
    "InvoicePaid event (or Simulate payment in demo mode). This is a testnet demo "
    "— no real funds move."
)

PAYMENTS_SYSTEM = (
    "You answer natural-language questions about this merchant's invoices and "
    "payments. Use only the JSON snapshot of invoices provided. Be concise. "
    "Cite invoice numbers (INV-0001) and statuses (pending, paid, overdue) "
    "exactly. If the snapshot does not contain the answer, say so.\n\n"
    + BOUNDARY
)

OVERVIEW_SYSTEM = (
    "You answer questions about this merchant's collection overview: totals, "
    "who is late, recent activity, and how SettleFlow works. Use only the JSON "
    "snapshot provided. Be concise. Do not invent customers, volume, or "
    "testimonials.\n\n"
    + BOUNDARY
)

MAX_HISTORY = 10


def _payments_snapshot(db: Session) -> dict:
    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer))
        .order_by(Invoice.created_at.desc())
        .limit(50)
        .all()
    )
    return {
        "today": date.today().isoformat(),
        "invoices": [
            {
                "invoice_number": inv.invoice_number,
                "customer": inv.customer.name if inv.customer else None,
                "company": inv.customer.company if inv.customer else None,
                "amount": inv.amount,
                "currency": inv.currency,
                "description": inv.description,
                "status": inv.status,
                "due_date": inv.due_date.isoformat(),
                "reminder_count": inv.reminder_count,
                "blockchain_tx_hash": inv.blockchain_tx_hash,
                "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
            }
            for inv in invoices
        ],
    }


def _overview_snapshot(db: Session) -> dict:
    invoices = db.query(Invoice).all()
    paid = [i for i in invoices if i.status == InvoiceStatus.paid.value]
    pending = [i for i in invoices if i.status == InvoiceStatus.pending.value]
    overdue = [i for i in invoices if i.status == InvoiceStatus.overdue.value]
    total_collected = sum(i.amount for i in paid)
    total_outstanding = sum(i.amount for i in pending)
    total_overdue = sum(i.amount for i in overdue)
    total = total_collected + total_outstanding + total_overdue
    collection_rate = round((total_collected / total * 100) if total else 0.0, 1)

    events = (
        db.query(ActivityEvent).order_by(ActivityEvent.created_at.desc()).limit(20).all()
    )
    return {
        "today": date.today().isoformat(),
        "summary": {
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
            "total_overdue": total_overdue,
            "paid_count": len(paid),
            "pending_count": len(pending),
            "overdue_count": len(overdue),
            "collection_rate": collection_rate,
        },
        "recent_activity": [
            {
                "event_type": e.event_type,
                "message": e.message,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "product": {
            "name": "SettleFlow",
            "purpose": "Automated invoice collection for Singapore freelancers billing overseas clients in USDC.",
            "parser_boundary": "The model only parses text into invoice fields. It never sends money or marks anything paid.",
            "paid_rule": "An invoice flips to paid only after the backend observes an on-chain InvoicePaid event.",
        },
    }


async def answer_query(
    db: Session,
    *,
    scope: ChatScope,
    message: str,
    history: list[dict[str, str]],
) -> str:
    if scope == "payments":
        system = PAYMENTS_SYSTEM
        snapshot = _payments_snapshot(db)
    else:
        system = OVERVIEW_SYSTEM
        snapshot = _overview_snapshot(db)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {
            "role": "system",
            "content": "Live snapshot:\n" + json.dumps(snapshot, default=str),
        },
    ]

    trimmed = history[-MAX_HISTORY:]
    for turn in trimmed:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message.strip()})
    return await chat_completions(messages)
