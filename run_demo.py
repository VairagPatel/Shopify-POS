"""Start the persistent mock and one FastAPI worker as a single deployable demo."""

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parent


# Fail before launch when another application already owns a requested port.
def available(port):
    """Fail before launch when another application already owns a requested port."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))


# Supervise both processes and preserve all application/mock state on disk.
def main():
    """Supervise both processes and preserve all application/mock state on disk."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--mock-port", type=int, default=8787)
    arguments = parser.parse_args()
    available(arguments.port)
    available(arguments.mock_port)
    runtime = Path(os.environ.get("ELUNO_RUNTIME", "runtime")).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("ELUNO_DB_PATH", str(runtime / "eluno.sqlite3"))
    os.environ["ELUNO_MOCK_URL"] = f"http://127.0.0.1:{arguments.mock_port}"
    from app.persistence.sqlite import SQLiteStore
    from app.security import initialize_security, provision_user

    store = SQLiteStore(os.environ["ELUNO_DB_PATH"])
    initialize_security(store)
    with store._connect() as connection:
        has_users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if not has_users:
        password = os.environ.get("ELUNO_ADMIN_PASSWORD")
        if not password:
            raise SystemExit(
                "No accounts. Run scripts/manage_users.py or set ELUNO_ADMIN_PASSWORD (12+ characters)."
            )
        provision_user(store, "admin", password, "admin", "*", "S108", "Demo owner")
    mock = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts/persistent_mock.py"),
            "--port",
            str(arguments.mock_port),
            "--snapshot",
            str(runtime / "mock-state.json"),
        ],
        cwd=ROOT,
    )
    application = None
    try:
        with httpx.Client(trust_env=False, timeout=1) as client:
            for _ in range(40):
                try:
                    if (
                        client.get(os.environ["ELUNO_MOCK_URL"] + "/health").status_code
                        == 200
                    ):
                        break
                except httpx.HTTPError:
                    time.sleep(0.15)
            else:
                raise RuntimeError("Mock failed to start")
        application = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                arguments.host,
                "--port",
                str(arguments.port),
                "--workers",
                "1",
            ],
            cwd=ROOT,
        )
        print(f"Eluno Store Studio: http://127.0.0.1:{arguments.port}", flush=True)
        while application.poll() is None and mock.poll() is None:
            time.sleep(0.5)
        if mock.poll() is not None:
            raise RuntimeError(
                "Mock exited; stopping app to avoid disconnected financial state"
            )
    finally:
        for process in (application, mock):
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
