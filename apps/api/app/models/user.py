from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """A freelancer. Owns customers and invoices; everything in the dashboard is
    scoped to exactly one of these."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Where this freelancer's invoices get paid. Falls back to MERCHANT_WALLET
    # at signup so the demo works before anyone has entered a real address.
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customers = relationship("Customer", back_populates="owner")
    invoices = relationship("Invoice", back_populates="owner")

    @property
    def display_name(self) -> str:
        return self.business_name or self.name
