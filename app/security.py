"""Password authentication, revocable sessions, and server-side store permissions."""

import hashlib
import hmac
import secrets
import time
from fastapi import HTTPException


# Derive a salted password hash without storing plaintext credentials.
def password_hash(password, salt=None):
    """Derive a salted password hash without storing plaintext credentials."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 600_000
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
        CREATE TABLE IF NOT EXISTS drafts(username TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS prescriptions(rx_id TEXT PRIMARY KEY, phone TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tills(id TEXT PRIMARY KEY, store_code TEXT NOT NULL, opened_at TEXT NOT NULL,
          closed_at TEXT, opening_paise INTEGER NOT NULL, counted_paise INTEGER, expected_paise INTEGER, variance_paise INTEGER);
        CREATE UNIQUE INDEX IF NOT EXISTS one_open_till ON tills(store_code) WHERE closed_at IS NULL;
        CREATE TABLE IF NOT EXISTS expenses(id TEXT PRIMARY KEY, till_id TEXT NOT NULL, amount_paise INTEGER NOT NULL,
          reason TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, subject TEXT NOT NULL,
          body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', error TEXT);
        CREATE TABLE IF NOT EXISTS timings(checkout_id TEXT PRIMARY KEY, elapsed_ms REAL NOT NULL, at TEXT NOT NULL);
        """)
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tills)")
        }
        if "baseline_json" not in columns:
            connection.execute(
                "ALTER TABLE tills ADD COLUMN baseline_json TEXT NOT NULL DEFAULT '[]'"
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
        if attempt and attempt["since"] > now - 900 and attempt["attempts"] >= 8:
            raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
        user = connection.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
        encoded = user["password_hash"] if user else "unknown:" + "0" * 64
        valid = verify_password(password, encoded)
        if not user or not valid:
            count = (
                attempt["attempts"] + 1
                if attempt and attempt["since"] > now - 900
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
            (hashlib.sha256(token.encode()).hexdigest(), username, csrf, now + 28800),
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
