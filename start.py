"""One-command local demo setup and launch: python start.py [runner options]."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


# Prepare an isolated interpreter and missing accounts without replacing existing data.
def main():
    if sys.version_info < (3, 10):
        raise SystemExit(
            "The app needs Python 3.10+; Python 3.13 is tested. The mock alone supports 3.8."
        )
    environment = ROOT / ".venv"
    interpreter = environment / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    if not interpreter.exists():
        venv.EnvBuilder(with_pip=True).create(environment)
    requirements = ROOT / "requirements.txt"
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = environment / ".eluno-requirements"
    if not marker.exists() or marker.read_text() != fingerprint:
        subprocess.run(
            [str(interpreter), "-m", "pip", "install", "-r", str(requirements)],
            cwd=ROOT,
            check=True,
        )
        marker.write_text(fingerprint)
    runtime = Path(os.environ.get("ELUNO_RUNTIME", str(ROOT / "runtime"))).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    environment_variables = {**os.environ, "ELUNO_RUNTIME": str(runtime)}
    environment_variables.setdefault("ELUNO_DB_PATH", str(runtime / "eluno.sqlite3"))
    subprocess.run(
        [str(interpreter), str(ROOT / "scripts/setup_demo.py")],
        cwd=ROOT,
        env=environment_variables,
        check=True,
    )
    if "--setup-only" in sys.argv[1:]:
        return
    try:
        subprocess.run(
            [str(interpreter), str(ROOT / "run_demo.py"), *sys.argv[1:]],
            cwd=ROOT,
            env=environment_variables,
            check=True,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
