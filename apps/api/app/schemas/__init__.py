from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    # 72 bytes is bcrypt's hard ceiling; anything longer is silently truncated.
    password: str = Field(min_length=8, max_length=72)
    business_name: Optional[str] = Field(default=None, max_length=255)
    wallet_address: Optional[str] = Field(default=None, max_length=42)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    business_name: Optional[str]
    wallet_address: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CustomerCreate(BaseModel):
    name: str
    email: EmailStr
    wallet_address: Optional[str] = None
    company: Optional[str] = None




class CustomerResponse(BaseModel):
    id: int
    name: str
    email: str
    wallet_address: Optional[str]
    company: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerImportResult(BaseModel):
    imported: int
    skipped: int
    customers: List[CustomerResponse] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ParsedCommand(BaseModel):
    customer_name: str
    amount: float
    currency: str
    description: str
    due_date: date
    confidence: float
    missing_fields: List[str] = Field(default_factory=list)


class ParseCommandRequest(BaseModel):
    command: str


class InvoiceCreate(BaseModel):
    customer_id: int
    amount: float
    currency: str = "USDC"
    description: str
    due_date: date


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    customer_id: int
    customer_name: Optional[str] = None
    merchant_wallet: str
    amount: float
    currency: str
    amount_wei_or_base_units: int
    description: str
    due_date: date
    status: str
    payment_url: Optional[str]
    payment_token: str
    blockchain_tx_hash: Optional[str]
    on_chain_invoice_id: Optional[str]
    created_at: datetime
    paid_at: Optional[datetime]
    reminder_count: int

    model_config = {"from_attributes": True}


class PaymentPageResponse(BaseModel):
    merchant_name: str
    invoice_number: str
    description: str
    amount: float
    currency: str
    due_date: date
    status: str
    customer_name: str
    payment_url: str
    payment_token: str
    on_chain_invoice_id: Optional[str]
    demo_mode: bool
    chain_configured: bool


class ActivityEventResponse(BaseModel):
    id: int
    invoice_id: Optional[int]
    event_type: str
    message: str
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NegotiationMessageCreate(BaseModel):
    message: str


class NegotiationMessageResponse(BaseModel):
    id: int
    invoice_id: int
    sender: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardSummary(BaseModel):
    total_collected: float
    total_outstanding: float
    total_overdue: float
    paid_count: int
    pending_count: int
    overdue_count: int
    collection_rate: float
    chart_data: List[Dict]
