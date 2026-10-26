"""Provider-neutral records at the application ports; all monetary fields use paise."""

from typing import TypedDict


class StoreRecord(TypedDict):
    id: int
    store_code: str
    kind: str
    invoice_prefix: str


class ProductRecord(TypedDict):
    id: int
    sku: str
    title: str
    price_paise: int
    inventory_item_id: int | None
    metadata: dict


class CustomerRecord(TypedDict):
    id: int
    phone: str
    first_name: str
    last_name: str
    tags: str


class PaymentRecord(TypedDict):
    kind: str
    status: str
    method: str
    amount_paise: int


class OrderLineRecord(TypedDict):
    id: int
    quantity: int
    kind: str | None
    gross_paise: int
    discount_paise: int
    tax_paise: int


class RefundRecord(TypedDict):
    id: int
    reference: str | None
    payments: list[PaymentRecord]


class OrderRecord(TypedDict):
    id: int
    location_id: int
    created_at: str
    cancelled: bool
    total_paise: int
    checkout_reference: str | None
    lines: list[OrderLineRecord]
    payments: list[PaymentRecord]
    refunds: list[RefundRecord]


class RefundCalculation(TypedDict):
    amount_paise: int
    maximum_paise: int
    tax_paise: int
    payment_parent: int | None
    payment_provider: str
