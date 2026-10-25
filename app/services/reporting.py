"""Day-end report from Shopify order records, not checkout SQLite rows."""

from datetime import date, datetime
from app.services.sale import paise


class ReportValidationError(ValueError):
    pass


class DayEndService:
    # Initialize the adapter or service with its explicit dependencies.
    def __init__(self, gateway):
        "Initialize the adapter or service with its explicit dependencies."
        self.gateway = gateway

    # Reconcile Shopify order-day totals while rejecting incomplete capped results.
    def report(self, store_code, day):
        "Reconcile Shopify order-day totals while rejecting incomplete capped results."
        target = date.fromisoformat(day) if isinstance(day, str) else day
        if not isinstance(target, date):
            raise ReportValidationError("date must be YYYY-MM-DD")
        loc = next(
            (
                x
                for x in self.gateway.locations()
                if x["eluno"]["store_code"] == store_code
                and x["eluno"]["kind"] == "store"
            ),
            None,
        )
        if loc is None:
            raise ReportValidationError("Unknown store")
        # Mock orders endpoint returns at most limit entries and has no pagination;
        # report is explicitly bounded, not silently labelled complete at scale.
        rows = self.gateway.orders(limit=250)
        if len(rows) >= 250:
            raise ReportValidationError(
                "Order result at cap; report cannot be certified complete"
            )
        matched = [
            o
            for o in rows
            if o.get("location_id") == loc["id"]
            and datetime.fromisoformat(o["created_at"]).date() == target
            and not o.get("cancelled_at")
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
            gross = sum(
                paise(line["price"]) * line["quantity"] for line in o["line_items"]
            )
            disc = sum(
                paise(line.get("total_discount", "0.00")) for line in o["line_items"]
            )
            tax = sum(
                paise(t["price"])
                for line in o["line_items"]
                for t in line.get("tax_lines", [])
            )
            total = paise(o["total_price"])
            if gross - disc != total:
                raise ReportValidationError(
                    "Order total not reconcilable: " + str(o["id"])
                )
            result["gross_paise"] += gross
            result["discounts_paise"] += disc
            result["tax_paise"] += tax
            result["taxable_paise"] += total - tax
            refunded = sum(
                paise(tx["amount"])
                for rf in o.get("refunds", [])
                for tx in rf.get("transactions", [])
                if tx.get("kind") == "refund"
            )
            result["refunds_paise"] += refunded
            for tx in o.get("transactions", []):
                if tx.get("kind") != "sale" or tx.get("status") != "success":
                    continue
                method = next(
                    (
                        x.get("value")
                        for x in o.get("note_attributes", [])
                        if x.get("name") == "payment_method"
                    ),
                    None,
                ) or tx.get("gateway", "unknown")
                result["payment_methods"][method] = result["payment_methods"].get(
                    method, 0
                ) + paise(tx["amount"])
        result["net_collected_paise"] = (
            sum(result["payment_methods"].values()) - result["refunds_paise"]
        )
        result["refund_timing_note"] = (
            "Refunds on these orders, regardless of refund date; not a refund-event-date cash ledger."
        )
        return result
