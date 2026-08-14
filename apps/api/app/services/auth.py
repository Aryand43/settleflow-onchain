from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.invoice import InvoiceCounter
from app.models.user import User

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    # bcrypt truncates silently past 72 bytes; reject rather than let two
    # different long passwords authenticate the same account.
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be 72 bytes or fewer")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash in the row — treat as a failed login, never a 500.
        return False


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.strip().lower()).first()


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    name: str,
    business_name: str | None = None,
    wallet_address: str | None = None,
) -> User:
    settings = get_settings()
    user = User(
        email=email.strip().lower(),
        password_hash=hash_password(password),
        name=name.strip(),
        business_name=(business_name or "").strip() or None,
        wallet_address=wallet_address or settings.merchant_wallet,
    )
    db.add(user)
    db.flush()

    # Give the account its invoice counter up front, in the same transaction.
    # The allocator can create one lazily, but doing it here means the very
    # first invoice never races to create it.
    db.add(InvoiceCounter(owner_id=user.id, next_value=1))

    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        # Hash anyway so a missing account and a wrong password take a similar
        # amount of time — otherwise the response time enumerates our users.
        hash_password("timing-equalizer")
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
