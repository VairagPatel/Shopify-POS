"""Store operations, evidence, and reporting for the authenticated demo."""

import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta, date
from uuid import uuid4
from fastapi import HTTPException
from app.gateways.http import MockHTTP
from app.services.sale import paise

INDIA = timezone(timedelta(hours=5, minutes=30))


# Use aware timestamps so store-day reporting is independent of host timezone.
def now_iso():
    """Use aware timestamps so store-day reporting is independent of host timezone."""
    return datetime.now(timezone.utc).isoformat()


# Map a Shopify timestamp onto the Bengaluru business calendar.
def store_day(timestamp):
    """Map a Shopify timestamp onto the Bengaluru business calendar."""
    return datetime.fromisoformat(timestamp).astimezone(INDIA).date().isoformat()


# Append a durable actor-attributed event without passwords or session tokens.
def audit(store, actor, action, reference, detail=None):
    """Append a durable actor-attributed event without passwords or session tokens."""
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO audit(at,actor,action,reference,detail) VALUES(?,?,?,?,?)",
            (now_iso(), actor, action, reference, json.dumps(detail or {})),
        )


# Return dictionaries from an internal parameterized read query.
def rows(store, sql, parameters=()):
    """Return dictionaries from an internal parameterized read query."""
    with store._connect() as connection:
        return [dict(row) for row in connection.execute(sql, parameters)]


class OperationsGateway(MockHTTP):
    """Overlay optometrist-entered prescriptions without changing the supplied mock."""

    # Bind a short-lived HTTP client and the local clinical record store.
    def __init__(self, store):
        """Bind a short-lived HTTP client and the local clinical record store."""
        super().__init__(os.environ.get("ELUNO_MOCK_URL", "http://127.0.0.1:8787"))
        self.store = store

    # Merge immutable source prescriptions with locally authored demo records.
    def prescriptions(self, phone):
        """Merge immutable source prescriptions with locally authored demo records."""
        local = rows(
            self.store, "SELECT payload FROM prescriptions WHERE phone=?", (phone,)
        )
        return super().prescriptions(phone) + [
            json.loads(row["payload"]) for row in local
        ]


# Fail explicitly when the mock's bounded API cannot certify a complete report.
def all_orders(gateway):
    """Fail explicitly when the mock's bounded API cannot certify a complete report."""
    orders = gateway.orders(limit=250)
    if len(orders) >= 250:
        raise HTTPException(
            422,
            "250-order mock API cap reached; archive the demo session before reporting.",
        )
    return orders


# Reconcile order-day sales and refund-event-day collections from Shopify records.
def analytics(gateway, day, store_code=None):
    """Reconcile order-day sales and refund-event-day collections from Shopify records."""
    date.fromisoformat(day)
    locations = [
        location
        for location in gateway.locations()
        if location["eluno"]["kind"] == "store"
    ]
    if store_code and store_code not in {
        location["eluno"]["store_code"] for location in locations
    }:
        raise ValueError("Unknown store")
    orders = all_orders(gateway)
    summaries = []
    for location in locations:
        code = location["eluno"]["store_code"]
        if store_code and code != store_code:
            continue
        store_orders = [
            order
            for order in orders
            if order.get("location_id") == location["id"]
            and not order.get("cancelled_at")
        ]
        sales = [
            order for order in store_orders if store_day(order["created_at"]) == day
        ]
        gross = sum(paise(order["subtotal_price"]) for order in sales)
        discounts = sum(paise(order["total_discounts"]) for order in sales)
        total = sum(paise(order["total_price"]) for order in sales)
        tax = sum(paise(order["total_tax"]) for order in sales)
        payments = sum(
            paise(transaction["amount"])
            for order in sales
            for transaction in order.get("transactions", [])
            if transaction.get("kind") == "sale"
            and transaction.get("status") == "success"
        )
        refunds = sum(
            paise(transaction["amount"])
            for order in store_orders
            for refund in order.get("refunds", [])
            if store_day(refund["created_at"]) == day
            for transaction in refund["transactions"]
        )
        channels = {}
        for order in sales:
            attributes = {
                item["name"]: item["value"] for item in order.get("note_attributes", [])
            }
            channel = attributes.get("channel", "unknown")
            channels[channel] = channels.get(channel, 0) + paise(order["total_price"])
        summaries.append(
            {
                "store_code": code,
                "name": location["name"],
                "bill_count": len(sales),
                "gross_paise": gross,
                "discounts_paise": discounts,
                "sales_paise": total,
                "tax_paise": tax,
                "taxable_paise": total - tax,
                "refunds_paise": refunds,
                "net_collected_paise": payments - refunds,
                "average_bill_paise": round(total / len(sales)) if sales else 0,
                "reconciliation_delta_paise": payments - total,
                "channels": channels,
                "order_ids": [order["id"] for order in sales],
            }
        )
    return {
        "date": day,
        "timezone": "Asia/Kolkata",
        "source": "Shopify mock",
        "stores": summaries,
        "refund_basis": "Refund event date; sales and channels use order date.",
    }


# Open exactly one drawer session per store with an explicit opening float.
def open_till(store, store_code, opening_paise):
    """Open exactly one drawer session per store with an explicit opening float."""
    identifier = str(uuid4())
    gateway = OperationsGateway(store)
    try:
        baseline = [
            str(transaction["id"])
            for order in all_orders(gateway)
            for transaction in order.get("transactions", [])
            + [
                transaction
                for refund in order.get("refunds", [])
                for transaction in refund["transactions"]
            ]
        ]
    finally:
        gateway.client.close()
    try:
        with store._connect() as connection:
            connection.execute(
                "INSERT INTO tills(id,store_code,opened_at,opening_paise,baseline_json) VALUES(?,?,?,?,?)",
                (
                    identifier,
                    store_code,
                    now_iso(),
                    opening_paise,
                    json.dumps(baseline),
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "A drawer is already open at this store") from exc
    return identifier


# Find the store's open drawer; absence is an explicit operational state.
def current_till(store, store_code):
    """Find the store's open drawer; absence is an explicit operational state."""
    matches = rows(
        store,
        "SELECT * FROM tills WHERE store_code=? AND closed_at IS NULL",
        (store_code,),
    )
    return matches[0] if matches else None


# Calculate expected physical cash from Shopify cash events and local expenses.
def till_summary(store, gateway, store_code):
    """Calculate expected physical cash from Shopify cash events and local expenses."""
    till = current_till(store, store_code)
    if not till:
        return {
            "open": False,
            "history": rows(
                store,
                "SELECT * FROM tills WHERE store_code=? ORDER BY opened_at DESC LIMIT 10",
                (store_code,),
            ),
        }
    location = next(
        item
        for item in gateway.locations()
        if item["eluno"]["store_code"] == store_code
    )
    baseline = set(json.loads(till["baseline_json"]))
    cash_in, cash_out = 0, 0
    for order in all_orders(gateway):
        if order.get("location_id") != location["id"]:
            continue
        attributes = {
            item["name"]: item["value"] for item in order.get("note_attributes", [])
        }
        if attributes.get("payment_method") != "cash":
            continue
        for transaction in order.get("transactions", []):
            if (
                transaction.get("kind") == "sale"
                and transaction.get("status") == "success"
                and str(transaction["id"]) not in baseline
            ):
                cash_in += paise(transaction["amount"])
        for refund in order.get("refunds", []):
            cash_out += sum(
                paise(transaction["amount"])
                for transaction in refund["transactions"]
                if str(transaction["id"]) not in baseline
            )
    expenses = rows(
        store, "SELECT * FROM expenses WHERE till_id=? ORDER BY at DESC", (till["id"],)
    )
    expense_total = sum(item["amount_paise"] for item in expenses)
    return {
        **till,
        "open": True,
        "cash_sales_paise": cash_in,
        "cash_refunds_paise": cash_out,
        "expenses": expenses,
        "expenses_paise": expense_total,
        "expected_paise": till["opening_paise"] + cash_in - cash_out - expense_total,
    }


# Queue one reviewable email per business event; delivery is a separate process.
def enqueue_email(store, identifier, subject, body):
    """Queue one reviewable email per business event; delivery is a separate process."""
    with store._connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO outbox(id,created_at,subject,body) VALUES(?,?,?,?)",
            (identifier, now_iso(), subject, body),
        )


# Close the drawer once and queue finance notification above the agreed threshold.
def close_till(store, gateway, store_code, counted_paise):
    """Close the drawer once and queue finance notification above the agreed threshold."""
    till = till_summary(store, gateway, store_code)
    if not till["open"]:
        raise HTTPException(409, "Open a drawer first")
    pending = rows(
        store,
        "SELECT checkout_id FROM checkouts WHERE store_code=? AND status NOT IN ('draft','cancelled','order_recorded')",
        (store_code,),
    )
    if pending:
        raise HTTPException(
            409, "Resolve pending payment/order exceptions before closing the drawer"
        )
    pending_refunds = rows(
        store,
        "SELECT r.refund_id FROM refund_attempts r JOIN checkouts c USING(checkout_id) WHERE c.store_code=? AND r.status NOT IN ('prepared','recorded')",
        (store_code,),
    )
    if pending_refunds:
        raise HTTPException(409, "Resolve uncertain refunds before closing the drawer")
    variance = counted_paise - till["expected_paise"]
    with store._connect() as connection:
        updated = connection.execute(
            "UPDATE tills SET closed_at=?,counted_paise=?,expected_paise=?,variance_paise=? WHERE id=? AND closed_at IS NULL",
            (now_iso(), counted_paise, till["expected_paise"], variance, till["id"]),
        )
        if updated.rowcount != 1:
            raise HTTPException(409, "Drawer was already closed")
    if abs(variance) > 20000:
        enqueue_email(
            store,
            "variance-" + till["id"],
            "Cash variance · " + store_code,
            f"Drawer {till['id']} variance: INR {variance / 100:.2f}. Counted: INR {counted_paise / 100:.2f}.",
        )
    return {
        **till,
        "open": False,
        "counted_paise": counted_paise,
        "variance_paise": variance,
        "flagged": abs(variance) > 20000,
    }


# Create an idempotent all-store digest suitable for the 10am scheduled job.
def founder_digest(store, gateway, day):
    """Create an idempotent all-store digest suitable for the 10am scheduled job."""
    report = analytics(gateway, day)
    lines = [
        "ELUNO / Yesterday at a glance",
        day,
        "Store | Bills | Average bill | Discounts",
    ]
    for item in report["stores"]:
        lines.append(
            f"{item['store_code']} | {item['bill_count']} | INR {item['average_bill_paise'] / 100:.2f} | INR {item['discounts_paise'] / 100:.2f}"
        )
    enqueue_email(
        store, "digest-" + day, "Eluno daily store report · " + day, "\n".join(lines)
    )
    return report
