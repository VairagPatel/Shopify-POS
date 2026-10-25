"""External service boundaries. Implementations start in later stages."""

from typing import Protocol, Optional, Sequence
from app.domain.models import Customer, Prescription, Cart, Invoice


class CommerceGateway(Protocol):
    # Define customer lookup independent of the external commerce provider.
    def find_customer_by_phone(self, phone: str) -> Optional[Customer]: ...
    # Define store-specific inventory lookup for physical frames.
    def get_frame_inventory(self, variant_id: str, store_code: str) -> int: ...
    # Define paid order creation against an explicit checkout reference.
    def create_order(
        self, checkout_id: str, cart: Cart, invoice: Invoice, payment_reference: str
    ) -> str: ...
    # Define safe order reconciliation without creating another order.
    def find_order_by_checkout_id(self, checkout_id: str) -> Optional[str]: ...
    # Define store-attributed refund creation in the commerce system.
    def refund_order(
        self, order_id: str, amount_paise: int, store_code: str
    ) -> str: ...
    # Define business-date order reads for source-based reporting.
    def list_orders(self, store_code: str, business_date: str) -> Sequence[dict]: ...


class StoreToolGateway(Protocol):
    # Select the most recently issued unexpired prescription.
    def latest_valid_prescription(self, phone: str) -> Optional[Prescription]: ...
    # Define authorization lookup for a staff member and requested action.
    def staff_authorized(self, staff_id: str, store_code: str, action: str) -> bool: ...


class TerminalGateway(Protocol):
    # Submit one terminal charge using the saved checkout payment reference.
    def charge(self, order_ref: str, amount_paise: int, payment_method: str) -> str: ...
    # Read a known terminal charge without causing another payment.
    def charge_status(self, charge_id: str) -> str: ...
    # Define a refund against an existing captured terminal charge.
    def refund(self, charge_id: str, amount_paise: int) -> str: ...
