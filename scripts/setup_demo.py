"""Create local reviewer accounts with generated passwords kept outside source control."""

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.persistence.sqlite import SQLiteStore
from app.security import initialize_security, provision_user


# Provision missing demonstration accounts without replacing existing credentials.
def main():
    """Provision missing demonstration accounts without replacing existing credentials."""
    store = SQLiteStore(
        os.environ.get("ELUNO_DB_PATH", str(ROOT / "runtime/eluno.sqlite3"))
    )
    initialize_security(store)
    credentials = []
    for username, role, store_code, staff, name in [
        ("admin", "admin", "*", "S108", "Demo owner"),
        ("manager", "manager", "HSR", "S108", "Meera · Manager"),
        ("cashier", "cashier", "HSR", "S105", "Vikram · Cashier"),
        ("finance", "finance", "*", "F001", "Finance reviewer"),
        ("optometrist", "optometrist", "HSR", "S107", "Aarav · Optometrist"),
    ]:
        with store._connect() as connection:
            exists = connection.execute(
                "SELECT username FROM users WHERE username=?", (username,)
            ).fetchone()
        if exists:
            continue
        password = secrets.token_urlsafe(16)
        provision_user(store, username, password, role, store_code, staff, name)
        credentials.append(f"{username}\t{password}\t{role}")
    destination = (
        Path(os.environ.get("ELUNO_RUNTIME", str(ROOT / "runtime")))
        / "demo-accounts.txt"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if credentials:
        with destination.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(credentials) + "\n")
    print(
        f"Accounts ready. Local credentials: {destination} (keep private, gitignored in default runtime)."
    )


if __name__ == "__main__":
    main()
