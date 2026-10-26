"""Executable billing ports using neutral records and opaque provider write snapshots."""

from typing import Protocol, runtime_checkable
from app.constants import MOCK_ORDER_LIMIT
from app.domain.models import Prescription
from app.domain.records import (
    StoreRecord,
    ProductRecord,
    CustomerRecord,
    OrderRecord,
    RefundCalculation,
)


@runtime_checkable
class ReportingGateway(Protocol):
    # Return source location mappings used to resolve a billing store.
    def locations(self) -> list[StoreRecord]: ...
    # Read the bounded source order collection without financial side effects.
    def orders(self, limit: int = MOCK_ORDER_LIMIT) -> list[OrderRecord]: ...


@runtime_checkable
class StoreToolGateway(Protocol):
    # Return source/local prescriptions; selection belongs to clinical domain logic.
    def prescriptions(self, phone: str) -> list[Prescription]: ...
    # Return staff records used to validate store and discount authority.
    def staff(self, store_code: str) -> list[dict]: ...


@runtime_checkable
class TerminalGateway(Protocol):
    # Execute one charge and return its provider reference.
    def charge(self, order_ref: str, amount_paise: int, method: str) -> dict: ...
    # Inspect a known provider charge without charging again.
    def charge_status(self, charge_id: str) -> dict: ...
    # Execute one reversal of a captured charge.
    def terminal_refund(
        self, charge_id: str, amount_paise: int, reason: str
    ) -> dict: ...


@runtime_checkable
class CommerceGateway(ReportingGateway, Protocol):
    # Resolve an existing customer by canonical phone.
    def customer(self, phone: str) -> dict | None: ...
    # Read catalog and clinical metadata for one variant.
    def variant(self, variant_id: int) -> dict: ...
    # Read available units at the chosen source location.
    def stock(self, item_id: int, location_id: int) -> int: ...
    # Record the persisted paid order once.
    def order(self, payload: dict) -> dict: ...
    # Read an original source sale for refund/reconciliation.
    def order_by_id(self, order_id: str) -> dict: ...
    # Obtain the source's original-tax reversal calculation.
    def refund_calculate(self, order_id: str, refund_lines: list[dict]) -> dict: ...
    # Record the prepared source refund once.
    def create_refund(self, order_id: str, refund: dict) -> dict: ...


@runtime_checkable
class SaleGateway(ReportingGateway, StoreToolGateway, Protocol):
    # Read existing write snapshots without leaking their provider schema to the workflow.
    def quote_inventory(self, quote: dict) -> tuple[int, list[tuple[int, int]]]: ...
    # Attach the captured transaction at the provider boundary.
    def paid_payload(self, quote: dict, charge_id: str) -> dict: ...
    # Translate a validated pricing result into the provider's persisted order representation.
    def build_order_payload(self, **pricing_context) -> dict: ...

    # Supply only the commerce reads and writes required by the sale workflow.
    def customer(self, phone: str) -> CustomerRecord | None: ...
    # Read the chosen product and lens metadata.
    def variant(self, variant_id: int) -> ProductRecord: ...
    # Validate inventory before any charge.
    def stock(self, item_id: int, location_id: int) -> int: ...
    # Record the paid order using its saved payload.
    def order(self, payload: dict) -> dict: ...
    # Execute the terminal charge once.
    def charge(self, order_ref: str, amount_paise: int, method: str) -> dict: ...


@runtime_checkable
class RefundGateway(Protocol):
    # Serialize only after the domain has checked original amount and tax totals.
    def build_refund_payload(
        self,
        lines: list[dict],
        calculation: RefundCalculation,
        reason: str,
        refund_id: str,
    ) -> dict: ...
    # Read the sale whose original tax and stock will be reversed.
    def order_by_id(self, order_id: str) -> OrderRecord: ...
    # Calculate a reversal before issuing money.
    def refund_calculate(
        self, order_id: str, refund_lines: list[dict]
    ) -> RefundCalculation: ...
    # Return captured funds through the terminal.
    def terminal_refund(
        self, charge_id: str, amount_paise: int, reason: str
    ) -> dict: ...
    # Record the tax/inventory reversal at the source.
    def create_refund(self, order_id: str, refund: dict) -> dict: ...
