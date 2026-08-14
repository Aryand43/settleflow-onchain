from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.services.auth import decode_access_token

DEMO_USER_EMAIL = "demo@settleflow.app"


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    settings = get_settings()
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolves the freelancer whose data this request may touch.

    Two ways in. A `Bearer` token is how the dashboard authenticates — that's
    the real path. `X-API-Key` resolves to the demo account instead, which is
    what keeps seed scripts, curl, and the smoke tests working without every
    one of them having to log in first.

    The API key is a development convenience: it grants full access to the demo
    account and nothing else, and it must not be the only thing standing between
    the internet and real user data. Never reuse it as a shared production
    secret.
    """
    settings = get_settings()

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        payload = decode_access_token(token)
        if payload is None:
            raise HTTPException(status_code=401, detail="Session expired — sign in again")
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Account no longer exists")
        return user

    if x_api_key and x_api_key == settings.api_key:
        user = db.query(User).filter(User.email == DEMO_USER_EMAIL).first()
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Demo account missing — run scripts/seed.py",
            )
        return user

    raise HTTPException(status_code=401, detail="Sign in to continue")
