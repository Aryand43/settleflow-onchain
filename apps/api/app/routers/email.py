from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import get_settings
from app.deps import get_current_user
from app.models.user import User
from app.services.email import email_delivery_configured

router = APIRouter(prefix="/email")


class EmailStatusResponse(BaseModel):
    configured: bool
    from_address: str | None = None


@router.get("/status", response_model=EmailStatusResponse)
def email_status(user: User = Depends(get_current_user)):
    """Lets the dashboard say "this writes a preview file" instead of "sent".

    Without this the UI had no way to know, so a button labelled "Send invoice
    email" reported success for an email that was only ever written to disk.
    """
    settings = get_settings()
    configured = email_delivery_configured()
    return EmailStatusResponse(
        configured=configured,
        from_address=settings.email_from if configured else None,
    )
