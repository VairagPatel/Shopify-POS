"""Local durable operational metadata; never the authoritative Shopify order ledger."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4
from app.domain.models import CheckoutStatus


class StateConflict(Exception):
    pass


class CheckoutNotFound(Exception):
    pass


class SQLiteStore:
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
                  updated_at TEXT NOT NULL
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
            """)

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
        updates = ["status=?", "updated_at=?"] + [f"{k}=?" for k in refs]
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE refund_attempts SET {','.join(updates)} WHERE refund_id=? AND status=?",
                (target, now, *refs.values(), refund_id, expected),
            )
        if cursor.rowcount != 1:
            raise StateConflict(
                "refund state changed; cannot repeat an external request"
            )
        return self.get_refund(refund_id)
