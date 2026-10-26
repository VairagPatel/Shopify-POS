"""Must-tier FULL refunds only. Protect side effects with a persistent state machine."""

import json
from uuid import uuid4
from app.domain.errors import StateConflict
from app.domain.errors import GatewayError
from app.gateways.contracts import RefundGateway
from app.persistence.contracts import RefundRepository


class RefundValidationError(ValueError):
    pass


class RefundService:
    # Initialize the adapter or service with its explicit dependencies.
    def __init__(self, store: RefundRepository, gateway: RefundGateway):
        "Initialize the adapter or service with its explicit dependencies."
        self.store, self.gateway = store, gateway

    # Validate the request and persist a quote before any financial side effect.
    def prepare(self, checkout_id, reason, refund_id=None):
        "Validate the request and persist a quote before any financial side effect."
        if not reason or not reason.strip():
            raise RefundValidationError("Refund reason required")
        checkout = self.store.get_checkout(checkout_id)
        if checkout["status"] != "order_recorded" or not checkout.get(
            "shopify_order_id"
        ):
            raise RefundValidationError("Only recorded Shopify sales can be refunded")
        order = self.gateway.order_by_id(checkout["shopify_order_id"])
        if order.get("refunds"):
            raise RefundValidationError(
                "Existing refund on order; full refund cannot be repeated"
            )
        charge = checkout.get("payment_charge_id")
        if not charge:
            raise RefundValidationError("No captured terminal charge reference")
        lines = []
        for line in order["lines"]:
            kind = line["kind"]
            if kind not in ("frame", "lens", "sunglass", "sunglasses"):
                raise RefundValidationError(
                    "Unknown line classification: manual check required"
                )
            lines.append(
                {
                    "line_id": line["id"],
                    "quantity": line["quantity"],
                    "restock": kind != "lens",
                    **({"location_id": order["location_id"]} if kind != "lens" else {}),
                }
            )
        if not lines or not order.get("location_id"):
            raise RefundValidationError("Missing order lines or billing location")
        calculated = self.gateway.refund_calculate(order["id"], lines)
        amount = calculated["amount_paise"]
        expected = order["total_paise"]
        if amount != expected or amount <= 0:
            raise RefundValidationError(
                f"Full refund mismatch: Shopify calculated {amount} paise vs sale {expected}"
            )
        maximum = calculated["maximum_paise"]
        if amount > maximum:
            raise RefundValidationError("Refund exceeds maximum refundable amount")
        expected_tax = sum(line["tax_paise"] for line in order["lines"])
        actual_tax = calculated["tax_paise"]
        if expected_tax != actual_tax:
            raise RefundValidationError(
                "Shopify refund tax does not reconcile with original order"
            )
        refund_identifier = refund_id or str(uuid4())
        payload = self.gateway.build_refund_payload(
            lines, calculated, reason, refund_identifier
        )
        row = self.store.initiate_refund(
            refund_identifier, checkout_id, order["id"], amount, payload
        )
        return {
            "refund_id": refund_identifier,
            "checkout_id": checkout_id,
            "status": row["status"],
            "amount_paise": amount,
            "tax_reversed_paise": actual_tax,
            "frame_restocked_on_shopify_success": True,
        }

    # Complete the persisted financial operation without repeating uncertain writes.
    def complete(self, refund_id):
        "Complete the persisted financial operation without repeating uncertain writes."
        row = self.store.get_refund(refund_id)
        if row["status"] == "recorded":
            return row
        if row["status"] != "prepared":
            raise StateConflict(
                "Refund already attempted: reconcile terminal/Shopify manually, do not retry"
            )
        checkout = self.store.get_checkout(row["checkout_id"])
        charge = checkout["payment_charge_id"]
        self.store.refund_transition(refund_id, "prepared", "terminal_pending")
        try:
            terminal = (
                {"refund_id": "cash-refund-" + refund_id}
                if charge.startswith("cash-")
                else self.gateway.terminal_refund(
                    charge, row["amount_paise"], "customer_return"
                )
            )
        except GatewayError as exc:
            self.store.refund_transition(
                refund_id,
                "terminal_pending",
                "terminal_uncertain",
                error_detail=str(exc),
            )
            raise
        self.store.refund_transition(
            refund_id,
            "terminal_pending",
            "terminal_refunded",
            terminal_refund_id=terminal["refund_id"],
        )
        self.store.refund_transition(refund_id, "terminal_refunded", "shopify_pending")
        try:
            refund = self.gateway.create_refund(
                row["shopify_order_id"], json.loads(row["payload_json"])
            )
        except GatewayError as exc:
            self.store.refund_transition(
                refund_id, "shopify_pending", "shopify_uncertain", error_detail=str(exc)
            )
            raise
        return self.store.refund_transition(
            refund_id,
            "shopify_pending",
            "recorded",
            shopify_refund_id=str(refund["id"]),
        )

    # Locate an uncertain refund by its saved reference without resubmitting.
    def reconcile_shopify(self, refund_id):
        "Locate an uncertain refund by its saved reference without resubmitting."
        row = self.store.get_refund(refund_id)
        if row["status"] != "shopify_uncertain":
            raise StateConflict("Only uncertain Shopify refunds may be reconciled")
        order = self.gateway.order_by_id(row["shopify_order_id"])
        matches = [
            source_refund
            for source_refund in order.get("refunds", [])
            if source_refund["reference"] == refund_id
        ]
        if len(matches) == 1:
            return self.store.refund_transition(
                refund_id,
                "shopify_uncertain",
                "recorded",
                shopify_refund_id=str(matches[0]["id"]),
            )
        if len(matches) > 1:
            return self.store.refund_transition(
                refund_id,
                "shopify_uncertain",
                "manual_review",
                error_detail="Multiple refunds for same reference",
            )
        return row
