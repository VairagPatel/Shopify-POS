"""Durable operation ports; workflows do not depend on SQLite connection details."""

from typing import Protocol
from app.domain.models import CheckoutStatus


class SaleRepository(Protocol):
    # Persist the initial operation identity.
    def create_checkout(
        self,
        store_code: str,
        customer_id: str | None = None,
        checkout_id: str | None = None,
    ) -> dict: ...
    # Read recovery state.
    def get_checkout(self, checkout_id: str) -> dict: ...
    # Claim a transition only if the old state still matches.
    def change_status(
        self,
        checkout_id: str,
        expected: CheckoutStatus,
        new: CheckoutStatus,
        *,
        error_detail: str | None = None,
    ) -> dict: ...
    # Store a uniquely linked external reference.
    def record_external_ref(self, checkout_id: str, field: str, value: str) -> dict: ...
    # Allocate one auditable store number per checkout.
    def reserve_invoice(
        self, checkout_id: str, store_code: str, prefix: str
    ) -> str: ...
    # Store the approved snapshot before payment.
    def save_quote(self, checkout_id: str, quote: dict): ...
    # Persist the opaque final order request before the external write.
    def save_order_submission(self, checkout_id: str, payload: dict): ...
    # Restore the approved snapshot after interruption.
    def load_quote(self, checkout_id: str) -> dict | None: ...
    # Complete the invoice allocation without exposing SQL to orchestration.
    def mark_invoice_issued(self, checkout_id: str): ...


class RefundRepository(Protocol):
    # Find the original recorded sale.
    def get_checkout(self, checkout_id: str) -> dict: ...
    # Persist reversal intent before moving money.
    def initiate_refund(
        self,
        refund_id: str,
        checkout_id: str,
        order_id: str,
        amount_paise: int,
        payload: dict,
    ) -> dict: ...
    # Restore refund state and immutable snapshot.
    def get_refund(self, refund_id: str) -> dict: ...
    # Claim the next reversal state with verified outcome references.
    def refund_transition(
        self, refund_id: str, expected: str, target: str, **refs
    ) -> dict: ...
