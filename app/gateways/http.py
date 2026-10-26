"""Concrete synchronous HTTP adapters for the *exercise mock*, isolated from pricing logic.

Only GET is retried for transport errors/429/503. Mutating requests are sent ONCE:
the supplied terminal mock does not actually guarantee idempotency by order_ref.
"""

import time
import httpx
from app.phone import normalize_phone
from app.domain.errors import GatewayError
from app.constants import (
    DEFAULT_MOCK_URL,
    HTTP_TIMEOUT_SECONDS,
    SAFE_READ_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    MAX_RETRY_DELAY_SECONDS,
    MOCK_ORDER_LIMIT,
    MOCK_SHOPIFY_API_PREFIX,
)


class MockHTTP:
    # Keep provider serialization behind the adapter instead of inside pricing orchestration.
    def build_order_payload(self, **pricing_context):
        from app.gateways.shopify_mapping import build_order_payload

        return build_order_payload(**pricing_context)

    # Initialize the adapter or service with its explicit dependencies.
    def __init__(
        self,
        base_url=DEFAULT_MOCK_URL,
        *,
        transport=None,
        timeout=HTTP_TIMEOUT_SECONDS,
        private_lookup=False,
    ):
        "Initialize the adapter or service with its explicit dependencies."
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"), transport=transport, timeout=timeout
        )
        self.private_lookup = private_lookup

    # Retry safe reads only; send financial mutations exactly once.
    def request(self, method, path, *, params=None, json=None):
        "Retry safe reads only; send financial mutations exactly once."
        safe = method.upper() == "GET"
        for attempt in range(SAFE_READ_ATTEMPTS if safe else 1):
            try:
                response = self.client.request(method, path, params=params, json=json)
            except httpx.RequestError as exc:
                if safe and attempt < SAFE_READ_ATTEMPTS - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise GatewayError(
                    f"{method} {path}: transport error: {exc}", uncertain=not safe
                ) from exc
            if (
                safe
                and response.status_code in (429, 503)
                and attempt < SAFE_READ_ATTEMPTS - 1
            ):
                time.sleep(
                    min(
                        float(
                            response.headers.get(
                                "Retry-After", str(RETRY_BACKOFF_SECONDS)
                            )
                        ),
                        MAX_RETRY_DELAY_SECONDS,
                    )
                )
                continue
            if not 200 <= response.status_code < 300:
                raise GatewayError(
                    f"{method} {path}: HTTP {response.status_code}: {response.text[:300]}",
                    status_code=response.status_code,
                    uncertain=(not safe and response.status_code >= 500),
                )
            return response.json()
        raise AssertionError("unreachable")

    # Prefix the mock Shopify API version and delegate transport handling.
    def shopify(self, method, path, **kw):
        "Prefix the mock Shopify API version and delegate transport handling."
        return self.request(method, MOCK_SHOPIFY_API_PREFIX + path.lstrip("/"), **kw)

    # Fetch the source store and warehouse location mappings.
    def locations(self):
        "Fetch the source store and warehouse location mappings."
        return self.shopify("GET", "locations.json")["locations"]

    # Look up an existing synthetic Shopify customer by exact phone.
    def customer(self, phone):
        "Look up an existing synthetic Shopify customer by exact phone."
        phone = normalize_phone(phone)
        if self.private_lookup:
            customers = self.request(
                "POST", "/eluno/customer-lookup", json={"phone": phone}
            )["customers"]
            return customers[0] if customers else None
        customers = self.shopify(
            "GET", "customers/search.json", params={"query": "phone:" + phone}
        )["customers"]
        return customers[0] if customers else None

    # Fetch source price, tax and clinical metadata for one variant.
    def variant(self, variant_id):
        "Fetch source price, tax and clinical metadata for one variant."
        return self.shopify("GET", f"variants/{variant_id}.json")["variant"]

    # Read the available quantity for one item at one store location.
    def stock(self, item_id, location_id):
        "Read the available quantity for one item at one store location."
        rows = self.shopify(
            "GET",
            "inventory_levels.json",
            params={"inventory_item_ids": item_id, "location_ids": location_id},
        )["inventory_levels"]
        return rows[0]["available"] if rows else 0

    # Retrieve all source prescriptions for the requested customer.
    def prescriptions(self, phone):
        "Retrieve all source prescriptions for the requested customer."
        phone = normalize_phone(phone)
        if self.private_lookup:
            return self.request(
                "POST", "/eluno/prescription-lookup", json={"phone": phone}
            )["prescriptions"]
        return self.request("GET", "/smt/prescriptions", params={"phone": phone})[
            "prescriptions"
        ]

    # Retrieve the store staff directory used for discount authorization.
    def staff(self, store_code):
        "Retrieve the store staff directory used for discount authorization."
        return self.request("GET", "/smt/staff", params={"store": store_code})["staff"]

    # Submit one terminal charge using the saved checkout payment reference.
    def charge(self, order_ref, amount_paise, method):
        "Submit one terminal charge using the saved checkout payment reference."
        return self.request(
            "POST",
            "/terminal/charges",
            json={
                "order_ref": order_ref,
                "amount_paise": amount_paise,
                "method": method,
            },
        )

    # Read a known terminal charge without causing another payment.
    def charge_status(self, charge_id):
        "Read a known terminal charge without causing another payment."
        return self.request("GET", f"/terminal/charges/{charge_id}")

    # Create a Shopify order using the already-validated persisted payload.
    def order(self, payload):
        "Create a Shopify order using the already-validated persisted payload."
        return self.shopify("POST", "orders.json", json={"order": payload})["order"]

    # Read the bounded source order collection for reporting and reconciliation.
    def orders(self, limit=MOCK_ORDER_LIMIT):
        "Read the bounded source order collection for reporting and reconciliation."
        return self.shopify(
            "GET", "orders.json", params={"status": "any", "limit": limit}
        )["orders"]

    # Fetch the original Shopify order for a locally linked checkout.
    def order_by_id(self, order_id):
        "Fetch the original Shopify order for a locally linked checkout."
        return self.shopify("GET", f"orders/{order_id}.json")["order"]

    # Ask Shopify to calculate refundable lines and original tax reversal.
    def refund_calculate(self, order_id, refund_lines):
        "Ask Shopify to calculate refundable lines and original tax reversal."
        return self.shopify(
            "POST",
            f"orders/{order_id}/refunds/calculate.json",
            json={"refund": {"refund_line_items": refund_lines}},
        )["refund"]

    # Submit one terminal refund against the captured charge.
    def terminal_refund(self, charge_id, amount_paise, reason):
        "Submit one terminal refund against the captured charge."
        return self.request(
            "POST",
            "/terminal/refunds",
            json={
                "charge_id": charge_id,
                "amount_paise": amount_paise,
                "reason": reason,
            },
        )

    # Record the tax and inventory reversal in the source Shopify order.
    def create_refund(self, order_id, refund):
        "Record the tax and inventory reversal in the source Shopify order."
        return self.shopify(
            "POST", f"orders/{order_id}/refunds.json", json={"refund": refund}
        )["refund"]
