"""Day-end report from Shopify order records, not checkout SQLite rows."""

from datetime import date, datetime
from app.constants import MOCK_ORDER_LIMIT, INDIA
from app.gateways.contracts import ReportingGateway


class ReportValidationError(ValueError):
    pass


class DayEndService:
    # Initialize the adapter or service with its explicit dependencies.
    def __init__(self, gateway: ReportingGateway):
        "Initialize the adapter or service with its explicit dependencies."
        self.gateway = gateway

    # Reconcile Shopify order-day totals while rejecting incomplete capped results.
    def report(self, store_code, day):
        "Reconcile Shopify order-day totals while rejecting incomplete capped results."
        target = date.fromisoformat(day) if isinstance(day, str) else day
        if not isinstance(target, date):
            raise ReportValidationError("date must be YYYY-MM-DD")
        location = next(
            (
                location_record
                for location_record in self.gateway.locations()
                if location_record["store_code"] == store_code
                and location_record["kind"] == "store"
            ),
            None,
        )
        if location is None:
            raise ReportValidationError("Unknown store")
        # Mock orders endpoint returns at most limit entries and has no pagination;
        # report is explicitly bounded, not silently labelled complete at scale.
        rows = self.gateway.orders(limit=MOCK_ORDER_LIMIT)
        if len(rows) >= MOCK_ORDER_LIMIT:
            raise ReportValidationError(
                "Order result at cap; report cannot be certified complete"
            )
        matched = [
            o
            for o in rows
            if o.get("location_id") == location["id"]
            and datetime.fromisoformat(o["created_at"]).astimezone(INDIA).date()
            == target
            and not o["cancelled"]
        ]
        result = {
            "store_code": store_code,
            "date": target.isoformat(),
            "source": "shopify",
            "bill_count": len(matched),
            "gross_paise": 0,
            "taxable_paise": 0,
            "tax_paise": 0,
            "discounts_paise": 0,
            "refunds_paise": 0,
            "net_collected_paise": 0,
            "payment_methods": {},
            "order_ids": [],
        }
        for o in matched:
            result["order_ids"].append(o["id"])
            gross = sum(line["gross_paise"] for line in o["lines"])
            disc = sum(line["discount_paise"] for line in o["lines"])
            tax = sum(line["tax_paise"] for line in o["lines"])
            total = o["total_paise"]
            if gross - disc != total:
                raise ReportValidationError(
                    "Order total not reconcilable: " + str(o["id"])
                )
            result["gross_paise"] += gross
            result["discounts_paise"] += disc
            result["tax_paise"] += tax
            result["taxable_paise"] += total - tax
            refunded = sum(
                tx["amount_paise"]
                for rf in o.get("refunds", [])
                for tx in rf["payments"]
                if tx.get("kind") == "refund" and tx.get("status") == "success"
            )
            result["refunds_paise"] += refunded
            for tx in o["payments"]:
                if tx.get("kind") != "sale" or tx.get("status") != "success":
                    continue
                method = tx["method"]
                result["payment_methods"][method] = (
                    result["payment_methods"].get(method, 0) + tx["amount_paise"]
                )
        result["net_collected_paise"] = (
            sum(result["payment_methods"].values()) - result["refunds_paise"]
        )
        result["refund_timing_note"] = (
            "Refunds on these orders, regardless of refund date; not a refund-event-date cash ledger."
        )
        return result
