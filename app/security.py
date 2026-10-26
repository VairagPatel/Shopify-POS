"""Password authentication, revocable sessions, and server-side store permissions."""

import hashlib
import hmac
import json
import secrets
import time
from fastapi import HTTPException
from app.constants import (
    PASSWORD_HASH_ITERATIONS,
    LOGIN_WINDOW_SECONDS,
    LOGIN_ATTEMPT_LIMIT,
    SESSION_DURATION_SECONDS,
)


# Derive a salted password hash without storing plaintext credentials.
def password_hash(password, salt=None):
    """Derive a salted password hash without storing plaintext credentials."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PASSWORD_HASH_ITERATIONS
    ).hex()
    return salt + ":" + digest


# Compare password hashes in constant time, including unknown-user attempts.
def verify_password(password, encoded):
    """Compare password hashes in constant time, including unknown-user attempts."""
    salt = encoded.split(":")[0]
    return hmac.compare_digest(password_hash(password, salt), encoded)


# Apply additive authentication and operations migrations to an existing database.
def initialize_security(store):
    """Apply additive authentication and operations migrations to an existing database."""
    with store._connect() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
          role TEXT NOT NULL, store_code TEXT NOT NULL, staff_id TEXT NOT NULL, display_name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, username TEXT NOT NULL,
          csrf TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(username TEXT PRIMARY KEY, attempts INTEGER NOT NULL, since REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
          actor TEXT NOT NULL, action TEXT NOT NULL, reference TEXT NOT NULL, detail TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS drafts(username TEXT PRIMARY KEY, payload TEXT NOT NULL,
          draft_id TEXT, created_by TEXT, created_by_staff_id TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS cart_snapshots(
          snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL, store_code TEXT NOT NULL, status TEXT NOT NULL,
          checkout_id TEXT, payload TEXT NOT NULL, saved_at TEXT NOT NULL,
          draft_id TEXT, created_by TEXT, created_by_staff_id TEXT, created_at TEXT, elapsed_ms REAL);
        CREATE INDEX IF NOT EXISTS cart_snapshots_user_time_idx
          ON cart_snapshots(username, saved_at DESC);
        CREATE VIEW IF NOT EXISTS cart_tracking AS
          SELECT snapshot.snapshot_id, snapshot.draft_id, snapshot.username,
                 snapshot.created_by, snapshot.created_by_staff_id, snapshot.store_code,
                 snapshot.status AS saved_status, checkout.status AS checkout_status,
                 snapshot.checkout_id, checkout.invoice_no, checkout.shopify_order_id,
                 snapshot.created_at, snapshot.saved_at, snapshot.elapsed_ms, snapshot.payload
          FROM cart_snapshots AS snapshot
          LEFT JOIN checkouts AS checkout ON checkout.checkout_id=snapshot.checkout_id;
        CREATE TABLE IF NOT EXISTS prescriptions(rx_id TEXT PRIMARY KEY, phone TEXT NOT NULL, payload TEXT NOT NULL,
          created_by TEXT, created_by_staff_id TEXT, created_at TEXT, store_code TEXT);
        CREATE TABLE IF NOT EXISTS tills(id TEXT PRIMARY KEY, store_code TEXT NOT NULL, opened_at TEXT NOT NULL,
          closed_at TEXT, opening_paise INTEGER NOT NULL, counted_paise INTEGER, expected_paise INTEGER, variance_paise INTEGER);
        CREATE UNIQUE INDEX IF NOT EXISTS one_open_till ON tills(store_code) WHERE closed_at IS NULL;
        CREATE TABLE IF NOT EXISTS expenses(id TEXT PRIMARY KEY, till_id TEXT NOT NULL, amount_paise INTEGER NOT NULL,
          reason TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS paid_ins(id TEXT PRIMARY KEY, till_id TEXT NOT NULL, amount_paise INTEGER NOT NULL CHECK(amount_paise > 0),
          reason TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, subject TEXT NOT NULL,
          body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', error TEXT);
        """)
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tills)")
        }
        if "baseline_json" not in columns:
            connection.execute(
                "ALTER TABLE tills ADD COLUMN baseline_json TEXT NOT NULL DEFAULT '[]'"
            )
        # Add attribution and lifecycle columns without replacing existing records.
        migrations = {
            "drafts": {
                "draft_id": "TEXT", "created_by": "TEXT", "created_by_staff_id": "TEXT",
                "created_at": "TEXT", "updated_at": "TEXT",
            },
            "cart_snapshots": {
                "draft_id": "TEXT", "created_by": "TEXT", "created_by_staff_id": "TEXT",
                "created_at": "TEXT", "elapsed_ms": "REAL",
            },
            "prescriptions": {
                "created_by": "TEXT", "created_by_staff_id": "TEXT", "created_at": "TEXT", "store_code": "TEXT",
            },
        }
        for table_name, new_columns in migrations.items():
            existing_columns = {
                row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})")
            }
            for column_name, column_type in new_columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )
        # Give legacy records stable IDs and best-effort actor/timestamp metadata.
        connection.execute(
            "UPDATE drafts SET draft_id=COALESCE(draft_id,'DR-LEGACY-'||username), "
            "created_by=COALESCE(created_by,username), "
            "created_by_staff_id=COALESCE(created_by_staff_id,(SELECT staff_id FROM users WHERE users.username=drafts.username)), "
            "created_at=COALESCE(created_at,json_extract(payload,'$.created_at'),json_extract(payload,'$.updated_at'),strftime('%Y-%m-%dT%H:%M:%SZ','now')), "
            "updated_at=COALESCE(updated_at,json_extract(payload,'$.updated_at'),created_at) "
            "WHERE draft_id IS NULL OR created_by IS NULL OR created_at IS NULL"
        )
        connection.execute(
            "UPDATE cart_snapshots SET draft_id=COALESCE(draft_id,(SELECT drafts.draft_id FROM drafts WHERE drafts.username=cart_snapshots.username),'DR-LEGACY-'||snapshot_id), "
            "created_by=COALESCE(created_by,username), "
            "created_by_staff_id=COALESCE(created_by_staff_id,(SELECT staff_id FROM users WHERE users.username=cart_snapshots.username)), "
            "created_at=COALESCE(created_at,(SELECT drafts.created_at FROM drafts WHERE drafts.username=cart_snapshots.username),saved_at) "
            "WHERE draft_id IS NULL OR created_by IS NULL OR created_at IS NULL"
        )
        connection.execute(
            "UPDATE prescriptions SET created_by=COALESCE(created_by,'legacy'), "
            "created_by_staff_id=COALESCE(created_by_staff_id,json_extract(payload,'$.optometrist_id')), "
            "created_at=COALESCE(created_at,json_extract(payload,'$.date')) "
            "WHERE created_by IS NULL OR created_at IS NULL"
        )
        # Fold existing checkout measurements into their checkout rows. The legacy
        # table is retained for safe rollback and old local database inspection.
        existing_tables = {
            row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        timing_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(checkouts)")
        }
        if "checkout_elapsed_ms" in timing_columns and "timings" in existing_tables:
            connection.execute(
                "UPDATE checkouts SET checkout_elapsed_ms=(SELECT elapsed_ms FROM timings WHERE timings.checkout_id=checkouts.checkout_id), "
                "timing_recorded_at=(SELECT at FROM timings WHERE timings.checkout_id=checkouts.checkout_id) "
                "WHERE checkout_elapsed_ms IS NULL AND EXISTS(SELECT 1 FROM timings WHERE timings.checkout_id=checkouts.checkout_id)"
            )
            # The old measurements now live on their checkout rows.
            connection.execute("DROP TABLE timings")
        # Upgrade a pre-existing inspection view once; avoid DDL on every request.
        view = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='view' AND name='cart_tracking'"
        ).fetchone()
        if not view or "snapshot.draft_id" not in view["sql"]:
            connection.execute("DROP VIEW IF EXISTS cart_tracking")
            connection.execute("""CREATE VIEW cart_tracking AS
              SELECT snapshot.snapshot_id, snapshot.draft_id, snapshot.username,
                     snapshot.created_by, snapshot.created_by_staff_id, snapshot.store_code,
                     snapshot.status AS saved_status, checkout.status AS checkout_status,
                     snapshot.checkout_id, checkout.invoice_no, checkout.shopify_order_id,
                     snapshot.created_at, snapshot.saved_at, snapshot.elapsed_ms, snapshot.payload
              FROM cart_snapshots AS snapshot
              LEFT JOIN checkouts AS checkout ON checkout.checkout_id=snapshot.checkout_id""")
        # Preserve pre-migration current carts as an initial inspectable snapshot once.
        for draft in connection.execute(
            "SELECT username,payload,draft_id,created_by,created_by_staff_id,created_at FROM drafts"
        ):
            existing = connection.execute(
                "SELECT 1 FROM cart_snapshots WHERE username=? AND payload=? LIMIT 1",
                (draft["username"], draft["payload"]),
            ).fetchone()
            if existing:
                continue
            try:
                payload = json.loads(draft["payload"])
            except (TypeError, json.JSONDecodeError):
                payload = {}
            connection.execute(
                "INSERT INTO cart_snapshots(username,store_code,status,checkout_id,payload,saved_at,draft_id,created_by,created_by_staff_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    draft["username"],
                    str(payload.get("store_code", "")),
                    "quoted" if payload.get("quote_id") else "draft",
                    payload.get("quote_id"),
                    draft["payload"],
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    draft["draft_id"],
                    draft["created_by"],
                    draft["created_by_staff_id"],
                    draft["created_at"],
                ),
            )


# Create or rotate an explicitly provisioned account; never seed public passwords.
def provision_user(store, username, password, role, store_code, staff_id, display_name):
    """Create or rotate an explicitly provisioned account; never seed public passwords."""
    if len(password) < 12:
        raise ValueError("Use a password of at least 12 characters")
    if role not in {"cashier", "manager", "finance", "optometrist", "admin"}:
        raise ValueError("Unknown role")
    initialize_security(store)
    with store._connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO users VALUES(?,?,?,?,?,?)",
            (
                username,
                password_hash(password),
                role,
                store_code,
                staff_id,
                display_name,
            ),
        )
        connection.execute("DELETE FROM sessions WHERE username=?", (username,))


# Rate-limit password attempts and issue an opaque, expiring session.
def login(store, username, password):
    """Rate-limit password attempts and issue an opaque, expiring session."""
    now = time.time()
    with store._connect() as connection:
        attempt = connection.execute(
            "SELECT * FROM login_attempts WHERE username=?", (username,)
        ).fetchone()
        if (
            attempt
            and attempt["since"] > now - LOGIN_WINDOW_SECONDS
            and attempt["attempts"] >= LOGIN_ATTEMPT_LIMIT
        ):
            raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
        user = connection.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
        encoded = user["password_hash"] if user else "unknown:" + "0" * 64
        valid = verify_password(password, encoded)
        if not user or not valid:
            count = (
                attempt["attempts"] + 1
                if attempt and attempt["since"] > now - LOGIN_WINDOW_SECONDS
                else 1
            )
            since = attempt["since"] if count > 1 else now
            connection.execute(
                "INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)",
                (username, count, since),
            )
            raise HTTPException(401, "Incorrect username or password")
        connection.execute("DELETE FROM login_attempts WHERE username=?", (username,))
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        connection.execute(
            "INSERT INTO sessions VALUES(?,?,?,?)",
            (
                hashlib.sha256(token.encode()).hexdigest(),
                username,
                csrf,
                now + SESSION_DURATION_SECONDS,
            ),
        )
    return token, csrf, public_user(user)


# Return identity fields safe to send to the browser.
def public_user(row):
    """Return identity fields safe to send to the browser."""
    return {
        key: row[key]
        for key in ("username", "role", "store_code", "staff_id", "display_name")
    }


# Resolve an unexpired session from its hashed token.
def authenticate(store, token):
    """Resolve an unexpired session from its hashed token."""
    if not token:
        raise HTTPException(401, "Please sign in")
    with store._connect() as connection:
        row = connection.execute(
            """SELECT users.*, sessions.csrf FROM sessions JOIN users USING(username)
          WHERE token_hash=? AND expires>?""",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
    if row is None:
        raise HTTPException(401, "Session expired. Please sign in again.")
    return {**public_user(row), "csrf": row["csrf"]}


# Reject unauthorized operations regardless of which buttons the UI shows.
def require_role(user, *roles):
    """Reject unauthorized operations regardless of which buttons the UI shows."""
    if user["role"] not in {*roles, "admin"}:
        raise HTTPException(403, "Your role cannot perform this action")


# Restrict store accounts while allowing central finance and administrators.
def require_store(user, store_code):
    """Restrict store accounts while allowing central finance and administrators."""
    if user["role"] not in {"admin", "finance"} and user["store_code"] != store_code:
        raise HTTPException(403, "This record belongs to another store")
