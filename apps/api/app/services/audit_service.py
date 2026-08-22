from __future__ import annotations

import logging
from typing import Any, Union

from sqlalchemy.orm import Session

from app.models.audit import InvoiceAuditEvent

logger = logging.getLogger(__name__)

Evidence = Union[dict[str, Any], str, None]


def log_invoice_event(
    db: Session,
    invoice_id: int,
    event_type: str,
    source: str,
    event_data: dict | None = None,
    evidence: Evidence = None,
) -> InvoiceAuditEvent | None:
    """Append-only write. Never raises; never updates/deletes existing rows.

    Call after the business transaction has committed (or on a read-only path)
    so a failed audit commit/rollback cannot undo invoice work.
    """
    try:
        if evidence is None:
            evidence_json: dict[str, Any] | None = None
        elif isinstance(evidence, str):
            evidence_json = {"text": evidence}
        else:
            evidence_json = evidence

        event = InvoiceAuditEvent(
            invoice_id=invoice_id,
            event_type=event_type,
            source=source,
            event_data=event_data,
            evidence=evidence_json,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except Exception:
        logger.exception(
            "Audit log failed for invoice_id=%s event_type=%s", invoice_id, event_type
        )
        try:
            db.rollback()
        except Exception:
            pass
        return None
