from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    # One directory per freelancer, and an email appears at most once in it —
    # which is what lets a CSV re-import update rather than duplicate.
    __table_args__ = (UniqueConstraint("owner_id", "email", name="uq_customer_owner_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    wallet_address: Mapped[Optional[str]] = mapped_column(String(42), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="customers")
    invoices = relationship("Invoice", back_populates="customer")
