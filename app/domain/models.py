"""Shopify-independent business vocabulary. Stage 3: no pricing or checkout behavior."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional, Tuple

Paise = int


class CheckoutStatus(str, Enum):
    DRAFT = "draft"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_UNCERTAIN = "payment_uncertain"
    PAYMENT_CAPTURED = "payment_captured"
    ORDER_PENDING = "order_pending"
    ORDER_UNCERTAIN = "order_uncertain"
    ORDER_RECORDED = "order_recorded"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Customer:
    customer_id: str
    phone: str
    tags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EyePower:
    sphere: str
    cylinder: str
    axis: Optional[int] = None
    add: Optional[str] = None


@dataclass(frozen=True)
class Prescription:
    prescription_id: str
    customer_phone: str
    right: EyePower
    left: EyePower
    valid_until: date
    issued_at: Optional[datetime] = None


@dataclass(frozen=True)
class LensConfiguration:
    lens_type: str
    index: str
    coating: str
    variant_id: str


@dataclass(frozen=True)
class CartLine:
    sku: str
    variant_id: str
    quantity: int
    unit_price_paise: Paise
    product_kind: str  # frame or lens, adapter maps external fields
    pair_ref: Optional[str] = None
    prescription_id: Optional[str] = None

    # Reject invalid quantity and negative money at the domain boundary.
    def __post_init__(self):
        "Reject invalid quantity and negative money at the domain boundary."
        if self.quantity <= 0 or self.unit_price_paise < 0:
            raise ValueError("quantity must be positive and money cannot be negative")


@dataclass(frozen=True)
class Cart:
    customer_id: str
    store_code: str
    lines: Tuple[CartLine, ...]


@dataclass(frozen=True)
class Offer:
    offer_id: str
    priority: int
    stackable: bool
    rule: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Invoice:
    invoice_no: str
    store_code: str
    checkout_id: str
    shopify_order_id: Optional[str] = None


@dataclass(frozen=True)
class Refund:
    refund_id: str
    invoice_no: str
    amount_paise: Paise
    reason: str
    status: str


@dataclass(frozen=True)
class TillSession:
    session_id: str
    store_code: str
    opening_float_paise: Paise
    status: str
