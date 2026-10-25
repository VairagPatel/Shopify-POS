"""Provision password-protected demo accounts using an interactive prompt or environment."""

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.persistence.sqlite import SQLiteStore
from app.security import provision_user


# Create an account without placing its password in shell arguments or source.
def main():
    """Create an account without placing its password in shell arguments or source."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument(
        "--role",
        choices=["admin", "manager", "cashier", "finance", "optometrist"],
        required=True,
    )
    parser.add_argument("--store", default="HSR")
    parser.add_argument("--staff", default="S108")
    parser.add_argument("--name", default="Demo user")
    arguments = parser.parse_args()
    password = os.environ.get("ELUNO_PROVISION_PASSWORD") or getpass.getpass(
        "Password (12+ characters): "
    )
    store = SQLiteStore(os.environ.get("ELUNO_DB_PATH", "runtime/eluno.sqlite3"))
    provision_user(
        store,
        arguments.username,
        password,
        arguments.role,
        arguments.store,
        arguments.staff,
        arguments.name,
    )
    print(
        f"Provisioned {arguments.username} ({arguments.role}). Existing sessions revoked."
    )


if __name__ == "__main__":
    main()
