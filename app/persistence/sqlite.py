"""Local durable operational metadata; never the authoritative Shopify order ledger."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4
from app.domain.models import CheckoutStatus


from app.domain.errors import StateConflict, CheckoutNotFound


class SQLiteStore:
    # Mark a retained invoice allocation issued without exposing SQL to the sale workflow.
    def mark_invoice_issued(self, checkout_id: str):
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            checkout = connection.execute("SELECT * FROM checkouts WHERE checkout_id=?", (checkout_id,)).fetchone()
            saved = connection.execute("SELECT quote_json FROM checkout_quotes WHERE checkout_id=?", (checkout_id,)).fetchone()
            if not checkout or checkout["status"] != "order_recorded" or not checkout["shopify_order_id"] or not saved:
                raise StateConflict("Only a recorded Shopify sale can issue an invoice")
            self._store_invoice(connection, dict(checkout), json.loads(saved["quote_json"]))
            connection.execute(
                "UPDATE invoice_allocations SET status='issued' WHERE checkout_id=?",
                (checkout_id,),
            )
            connection.commit()

    # Keep the exact opaque order write before sending it to the commerce adapter.
    def save_order_submission(self, checkout_id: str, payload: dict):
        encoded = json.dumps(payload, sort_keys=True)
        with self._connect() as connection:
            existing = connection.execute("SELECT payload_json FROM order_submissions WHERE checkout_id=?", (checkout_id,)).fetchone()
            if existing and existing["payload_json"] != encoded:
                raise StateConflict("The order submission is immutable once saved")
            connection.execute(
                "INSERT OR IGNORE INTO order_submissions(checkout_id,payload_json,created_at) VALUES(?,?,?)",
                (checkout_id, encoded, datetime.now(timezone.utc).isoformat()),
            )

    # Materialize an issued invoice from its already persisted checkout and line snapshot.
    def _store_invoice(self, connection, checkout, quote):
        lines = quote.get("lines") or []
        if not lines:
            from app.domain.money import paise
            for line in quote.get("order_payload", {}).get("line_items", []):
                props = {item["name"]: item["value"] for item in line.get("properties", [])}
                taxes = {tax["title"]: paise(tax["price"]) for tax in line.get("tax_lines", [])}
                lines.append({
                    "variant_id": line["variant_id"], "title": str(line["variant_id"]),
                    "gross_paise": paise(line["price"]) * line.get("quantity", 1),
                    "discount_paise": paise(line.get("total_discount", "0.00")),
                    "cgst_paise": taxes.get("CGST", 0), "sgst_paise": taxes.get("SGST", 0),
                    "hsn": props.get("hsn"), "rx_id": props.get("rx_id"),
                    "wearer_phone": props.get("wearer_phone"),
                })
        gross = sum(line["gross_paise"] for line in lines)
        discount = sum(line["discount_paise"] for line in lines)
        tax = sum(line["cgst_paise"] + line["sgst_paise"] for line in lines)
        submission = connection.execute("SELECT payload_json FROM order_submissions WHERE checkout_id=?", (checkout["checkout_id"],)).fetchone()
        snapshot = {**quote, "lines": lines, "checkout": checkout}
        connection.execute(
            "INSERT OR IGNORE INTO invoices(invoice_no,checkout_id,store_code,shopify_order_id,issued_at,payment_method,"
            "gross_paise,discount_paise,taxable_paise,tax_paise,total_paise,payment_charge_id,payload_json,order_submission_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (checkout["invoice_no"], checkout["checkout_id"], checkout["store_code"], checkout["shopify_order_id"],
             checkout["updated_at"], quote.get("method", "unknown"), gross, discount, gross-discount-tax, tax,
             quote["total_paise"], checkout["payment_charge_id"], json.dumps(snapshot),
             submission["payload_json"] if submission else None),
        )

    # Read the durable invoice record shown by the existing bill detail endpoint.
    def get_invoice(self, checkout_id: str):
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM invoices WHERE checkout_id=?", (checkout_id,)).fetchone()
        return dict(row) if row else None

    # Initialize the adapter or service with its explicit dependencies.
    def __init__(self, path: str):
        "Initialize the adapter or service with its explicit dependencies."
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    # Open SQLite with named rows and a bounded lock wait.
    def _connect(self):
        "Open SQLite with named rows and a bounded lock wait."
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=15000")
        return connection

    # Create missing operational tables without replacing existing records.
    def _initialize(self):
        "Create missing operational tables without replacing existing records."
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS checkouts (
                  checkout_id TEXT PRIMARY KEY,
                  store_code TEXT NOT NULL,
                  customer_id TEXT,
                  status TEXT NOT NULL,
                  payment_ref TEXT UNIQUE,
                  payment_charge_id TEXT,
                  shopify_order_id TEXT UNIQUE,
                  invoice_no TEXT UNIQUE,
                  error_detail TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  checkout_elapsed_ms REAL,
                  timing_recorded_at TEXT
                );
                CREATE TABLE IF NOT EXISTS checkout_quotes (
                  checkout_id TEXT PRIMARY KEY REFERENCES checkouts(checkout_id),
                  quote_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS invoice_series (
                  store_code TEXT PRIMARY KEY,
                  prefix TEXT NOT NULL,
                  next_number INTEGER NOT NULL CHECK (next_number > 0)
                );
                CREATE TABLE IF NOT EXISTS invoice_allocations (
                  invoice_no TEXT PRIMARY KEY,
                  checkout_id TEXT NOT NULL UNIQUE REFERENCES checkouts(checkout_id),
                  store_code TEXT NOT NULL,
                  serial_number INTEGER NOT NULL,
                  allocated_at TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'reserved',
                  UNIQUE(store_code, serial_number)
                );
                CREATE TABLE IF NOT EXISTS refund_attempts (
                  refund_id TEXT PRIMARY KEY,
                  checkout_id TEXT NOT NULL UNIQUE REFERENCES checkouts(checkout_id),
                  shopify_order_id TEXT NOT NULL,
                  amount_paise INTEGER NOT NULL,
                  payload_json TEXT NOT NULL,
                  status TEXT NOT NULL,
                  terminal_refund_id TEXT,
                  shopify_refund_id TEXT,
                  error_detail TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS checkout_store_idx ON checkouts(store_code, status);
                CREATE TABLE IF NOT EXISTS order_submissions(
                  checkout_id TEXT PRIMARY KEY REFERENCES checkouts(checkout_id),
                  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS invoices(
                  invoice_no TEXT PRIMARY KEY, checkout_id TEXT UNIQUE NOT NULL REFERENCES checkouts(checkout_id),
                  store_code TEXT NOT NULL, shopify_order_id TEXT UNIQUE NOT NULL, issued_at TEXT NOT NULL,
                  payment_method TEXT NOT NULL, gross_paise INTEGER NOT NULL, discount_paise INTEGER NOT NULL,
                  taxable_paise INTEGER NOT NULL, tax_paise INTEGER NOT NULL, total_paise INTEGER NOT NULL,
                  payment_charge_id TEXT, payload_json TEXT NOT NULL, order_submission_json TEXT);
                CREATE VIEW IF NOT EXISTS invoice_lines AS
                  SELECT invoice.invoice_no, invoice.checkout_id, invoice.store_code,
                         line.key + 1 AS line_number,
                         json_extract(line.value,'$.variant_id') AS variant_id,
                         json_extract(line.value,'$.title') AS title,
                         json_extract(line.value,'$.hsn') AS hsn,
                         json_extract(line.value,'$.gross_paise') AS gross_paise,
                         json_extract(line.value,'$.discount_paise') AS discount_paise,
                         json_extract(line.value,'$.cgst_paise') AS cgst_paise,
                         json_extract(line.value,'$.sgst_paise') AS sgst_paise,
                         json_extract(line.value,'$.rx_id') AS rx_id,
                         json_extract(line.value,'$.wearer_phone') AS wearer_phone
                  FROM invoices invoice, json_each(invoice.payload_json,'$.lines') line;
                CREATE TABLE IF NOT EXISTS refund_events(
                  event_id INTEGER PRIMARY KEY AUTOINCREMENT, refund_id TEXT NOT NULL,
                  previous_status TEXT, status TEXT NOT NULL, at TEXT NOT NULL, detail_json TEXT NOT NULL);
            """)
            checkout_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(checkouts)")
            }
            if "checkout_elapsed_ms" not in checkout_columns:
                connection.execute("ALTER TABLE checkouts ADD COLUMN checkout_elapsed_ms REAL")
            if "timing_recorded_at" not in checkout_columns:
                connection.execute("ALTER TABLE checkouts ADD COLUMN timing_recorded_at TEXT")
            refund_columns = {row["name"] for row in connection.execute("PRAGMA table_info(refund_attempts)")}
            if "synced_at" not in refund_columns:
                connection.execute("ALTER TABLE refund_attempts ADD COLUMN synced_at TEXT")
            connection.execute("UPDATE refund_attempts SET synced_at=updated_at WHERE status='recorded' AND synced_at IS NULL")
            # Backfill only real completed POS sales; drafts and seeded web orders are not invoices.
            for saved in connection.execute(
                "SELECT c.*,q.quote_json FROM checkouts c JOIN checkout_quotes q USING(checkout_id) "
                "LEFT JOIN invoices i USING(checkout_id) WHERE c.status='order_recorded' AND i.checkout_id IS NULL "
                "AND c.invoice_no IS NOT NULL AND c.shopify_order_id IS NOT NULL"
            ).fetchall():
                self._store_invoice(connection, dict(saved), json.loads(saved["quote_json"]))
                connection.execute("UPDATE invoice_allocations SET status='issued' WHERE checkout_id=?", (saved["checkout_id"],))
            connection.execute("UPDATE invoice_allocations SET status='issued' WHERE checkout_id IN (SELECT checkout_id FROM invoices)")
            connection.execute(
                "INSERT INTO refund_events(refund_id,previous_status,status,at,detail_json) "
                "SELECT r.refund_id,NULL,r.status,r.updated_at,'{\"migration\":\"existing state\"}' FROM refund_attempts r "
                "WHERE NOT EXISTS(SELECT 1 FROM refund_events e WHERE e.refund_id=r.refund_id)"
            )

    # Persist a uniquely identified draft before external writes begin.
    def create_checkout(
        self,
        store_code: str,
        customer_id: Optional[str] = None,
        checkout_id: Optional[str] = None,
    ):
        "Persist a uniquely identified draft before external writes begin."
        if not store_code.strip():
            raise ValueError("store_code required")
        checkout_identifier = checkout_id or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO checkouts(checkout_id,store_code,customer_id,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (
                        checkout_identifier,
                        store_code,
                        customer_id,
                        CheckoutStatus.DRAFT.value,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise StateConflict("checkout already exists") from exc
        return self.get_checkout(checkout_identifier)

    # Load one checkout or raise an explicit missing-record error.
    def get_checkout(self, checkout_id: str):
        "Load one checkout or raise an explicit missing-record error."
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM checkouts WHERE checkout_id=?", (checkout_id,)
            ).fetchone()
        if row is None:
            raise CheckoutNotFound(checkout_id)
        return dict(row)

    # Compare-and-set prevents concurrent workers from silently overwriting state.
    def change_status(
        self,
        checkout_id: str,
        expected: CheckoutStatus,
        new: CheckoutStatus,
        *,
        error_detail: Optional[str] = None,
    ):
        """Compare-and-set prevents concurrent workers from silently overwriting state."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE checkouts SET status=?,error_detail=?,updated_at=? WHERE checkout_id=? AND status=?",
                (new.value, error_detail, now, checkout_id, expected.value),
            )
        if cursor.rowcount != 1:
            raise StateConflict("checkout missing or status changed")
        return self.get_checkout(checkout_id)

    # Store an immutable external reference with uniqueness protection.
    def record_external_ref(self, checkout_id: str, field: str, value: str):
        "Store an immutable external reference with uniqueness protection."
        if field not in {"payment_ref", "payment_charge_id", "shopify_order_id"}:
            raise ValueError("unsupported external reference")
        with self._connect() as connection:
            try:
                cursor = connection.execute(
                    f"UPDATE checkouts SET {field}=?,updated_at=? WHERE checkout_id=? AND ({field} IS NULL OR {field}=?)",
                    (value, datetime.now(timezone.utc).isoformat(), checkout_id, value),
                )
            except sqlite3.IntegrityError as exc:
                raise StateConflict("external reference already assigned") from exc
        if cursor.rowcount != 1:
            raise StateConflict("conflicting reference or checkout missing")
        return self.get_checkout(checkout_id)

    # Idempotent, serialized per-store numbering. Reserved numbers are auditable, never recycled.
    def reserve_invoice(self, checkout_id: str, store_code: str, prefix: str):
        """Idempotent, serialized per-store numbering. Reserved numbers are auditable, never recycled."""
        if not store_code or not prefix:
            raise ValueError("store and prefix required")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                checkout = connection.execute(
                    "SELECT store_code,invoice_no FROM checkouts WHERE checkout_id=?",
                    (checkout_id,),
                ).fetchone()
                if checkout is None:
                    raise CheckoutNotFound(checkout_id)
                if checkout["store_code"] != store_code:
                    raise StateConflict("checkout belongs to different store")
                if checkout["invoice_no"]:
                    connection.execute("COMMIT")
                    return checkout["invoice_no"]
                series = connection.execute(
                    "SELECT prefix,next_number FROM invoice_series WHERE store_code=?",
                    (store_code,),
                ).fetchone()
                if series is None:
                    number = 1
                    connection.execute(
                        "INSERT INTO invoice_series(store_code,prefix,next_number) VALUES(?,?,?)",
                        (store_code, prefix, 2),
                    )
                else:
                    if series["prefix"] != prefix:
                        raise StateConflict("invoice prefix mismatch")
                    number = series["next_number"]
                    connection.execute(
                        "UPDATE invoice_series SET next_number=? WHERE store_code=?",
                        (number + 1, store_code),
                    )
                invoice_no = f"{prefix}{number:06d}"
                now = datetime.now(timezone.utc).isoformat()
                connection.execute(
                    "INSERT INTO invoice_allocations(invoice_no,checkout_id,store_code,serial_number,allocated_at) VALUES(?,?,?,?,?)",
                    (invoice_no, checkout_id, store_code, number, now),
                )
                connection.execute(
                    "UPDATE checkouts SET invoice_no=?,updated_at=? WHERE checkout_id=?",
                    (invoice_no, now, checkout_id),
                )
                connection.execute("COMMIT")
                return invoice_no
            except Exception:
                connection.execute("ROLLBACK")
                raise

    # Return the complete ordered allocation register for one store.
    def invoice_allocations(self, store_code: str):
        "Return the complete ordered allocation register for one store."
        with self._connect() as connection:
            return [
                dict(r)
                for r in connection.execute(
                    "SELECT * FROM invoice_allocations WHERE store_code=? ORDER BY serial_number",
                    (store_code,),
                )
            ]

    # Persist an immutable quote only while the checkout is still a draft.
    def save_quote(self, checkout_id: str, quote: dict):
        "Persist an immutable quote only while the checkout is still a draft."
        with self._connect() as connection:
            current = connection.execute(
                "SELECT status FROM checkouts WHERE checkout_id=?", (checkout_id,)
            ).fetchone()
            if not current or current["status"] != CheckoutStatus.DRAFT.value:
                raise StateConflict("Only draft checkout can accept a quote")
            try:
                connection.execute(
                    "INSERT INTO checkout_quotes(checkout_id,quote_json) VALUES(?,?)",
                    (checkout_id, json.dumps(quote)),
                )
            except sqlite3.IntegrityError as exc:
                raise StateConflict("Quote already persisted") from exc

    # Load the quote used for charging and creating the source order.
    def load_quote(self, checkout_id: str):
        "Load the quote used for charging and creating the source order."
        with self._connect() as connection:
            row = connection.execute(
                "SELECT quote_json FROM checkout_quotes WHERE checkout_id=?",
                (checkout_id,),
            ).fetchone()
        return json.loads(row["quote_json"]) if row else None

    # Reserve one refund attempt per checkout before any money moves.
    def initiate_refund(self, refund_id, checkout_id, order_id, amount_paise, payload):
        "Reserve one refund attempt per checkout before any money moves."
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO refund_attempts(refund_id,checkout_id,shopify_order_id,amount_paise,payload_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        refund_id,
                        checkout_id,
                        str(order_id),
                        amount_paise,
                        json.dumps(payload),
                        "prepared",
                        now,
                        now,
                    ),
                )
                connection.execute("INSERT INTO refund_events(refund_id,previous_status,status,at,detail_json) VALUES(?,?,?,?,?)",
                                   (refund_id, None, "prepared", now, "{}"))
                connection.commit()
            except sqlite3.IntegrityError as exc:
                raise StateConflict("refund reference already exists") from exc
        return self.get_refund(refund_id)

    # Load the durable refund state or report an unknown reference.
    def get_refund(self, refund_id):
        "Load the durable refund state or report an unknown reference."
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM refund_attempts WHERE refund_id=?", (refund_id,)
            ).fetchone()
        if row is None:
            raise CheckoutNotFound("refund " + refund_id)
        return dict(row)

    # Compare-and-set refund state and allow only known external-reference fields.
    def refund_transition(self, refund_id, expected, target, **refs):
        "Compare-and-set refund state and allow only known external-reference fields."
        allowed = {"terminal_refund_id", "shopify_refund_id", "error_detail"}
        if set(refs) - allowed:
            raise ValueError("unsupported refund field")
        now = datetime.now(timezone.utc).isoformat()
        if target == "recorded":
            refs = {**refs, "synced_at": now}
        updates = ["status=?", "updated_at=?"] + [f"{k}=?" for k in refs]
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                f"UPDATE refund_attempts SET {','.join(updates)} WHERE refund_id=? AND status=?",
                (target, now, *refs.values(), refund_id, expected),
            )
            if cursor.rowcount != 1:
                raise StateConflict("refund state changed; cannot repeat an external request")
            connection.execute("INSERT INTO refund_events(refund_id,previous_status,status,at,detail_json) VALUES(?,?,?,?,?)",
                               (refund_id, expected, target, now, json.dumps(refs)))
            connection.commit()
        return self.get_refund(refund_id)
