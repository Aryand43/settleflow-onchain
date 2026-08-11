from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.schemas import CustomerCreate


class CustomerRepository(Protocol):
    def list_customers(self, db: Session) -> list[Customer]: ...
    def find_by_name(self, db: Session, name: str) -> Customer | None: ...
    def create(self, db: Session, data: CustomerCreate) -> Customer: ...


class LocalMockCustomerRepository:
    """Local fallback customer directory for prototype demos."""

    def list_customers(self, db: Session) -> list[Customer]:
        return db.query(Customer).order_by(Customer.name).all()

    def find_by_name(self, db: Session, name: str) -> Customer | None:
        normalized = name.strip().lower()
        for customer in db.query(Customer).all():
            if customer.name.lower() == normalized:
                return customer
            if normalized in customer.name.lower() or customer.name.lower() in normalized:
                return customer
        return None

    def create(self, db: Session, data: CustomerCreate) -> Customer:
        customer = Customer(
            name=data.name,
            email=str(data.email),
            wallet_address=data.wallet_address,
            company=data.company,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer


def get_customer_repository() -> CustomerRepository:
    return LocalMockCustomerRepository()
