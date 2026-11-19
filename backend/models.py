from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field


class LineItemPatch(BaseModel):
    description: str = Field(max_length=500)
    quantity: float = Field(default=1, ge=0)
    sku: str | None = Field(default=None, max_length=128)
    unit: str | None = Field(default=None, max_length=64)
    unit_price: float | None = None
    discount: float | None = None
    tax_rate: float | None = Field(default=None, ge=0, le=100)
    tax_amount: float | None = None
    amount: float
    line_total: float | None = None


class DocumentPatch(BaseModel):
    document_type: str | None = Field(default=None, pattern=r"^(receipt|invoice|bill)$")
    document_subtype: str | None = Field(default=None, max_length=64)
    vendor_name: str | None = Field(default=None, max_length=500)
    vendor_address: str | None = Field(default=None, max_length=1000)
    vendor_tax_id: str | None = Field(default=None, max_length=128)
    customer_name: str | None = Field(default=None, max_length=500)
    customer_address: str | None = Field(default=None, max_length=1000)
    bill_to_name: str | None = Field(default=None, max_length=500)
    bill_to_address: str | None = Field(default=None, max_length=1000)
    ship_to_name: str | None = Field(default=None, max_length=500)
    ship_to_address: str | None = Field(default=None, max_length=1000)
    document_number: str | None = Field(default=None, max_length=128)
    original_invoice_number: str | None = Field(default=None, max_length=128)
    issue_date: str | None = Field(default=None, max_length=64)
    due_date: str | None = Field(default=None, max_length=64)
    account_number: str | None = Field(default=None, max_length=128)
    purchase_order_number: str | None = Field(default=None, max_length=128)
    payment_terms: str | None = Field(default=None, max_length=256)
    service_period_start: str | None = Field(default=None, max_length=64)
    service_period_end: str | None = Field(default=None, max_length=64)
    autopay_date: str | None = Field(default=None, max_length=64)
    merchant: str | None = Field(default=None, max_length=500)
    date: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    receipt_number: str | None = Field(default=None, max_length=128)
    card_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    gross_amount: float | None = None
    discount: float | None = None
    refund: float | None = None
    subtotal: float | None = None
    shipping: float | None = None
    fees: float | None = None
    tax: float | None = None
    tip: float | None = None
    total: float | None = None
    amount_paid: float | None = None
    balance_due: float | None = None
    previous_balance: float | None = None
    payments: float | None = None
    credits: float | None = None
    adjustments: float | None = None
    current_charges: float | None = None
    late_fee: float | None = None
    minimum_due: float | None = None
    payment_method: str | None = Field(default=None, max_length=128)
    items: list[LineItemPatch] | None = Field(default=None, max_length=500)


class BatchCreateRequest(BaseModel):
    name: str = Field(default="", max_length=160)


class BatchDocumentDeleteRequest(BaseModel):
    document_ids: list[
        Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
    ] = Field(min_length=1, max_length=100)


class HistoryPromoteRequest(BaseModel):
    source_type: str = Field(pattern=r"^(single|batch)$")
    document_id: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
