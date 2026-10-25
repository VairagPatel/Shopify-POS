"""Run the supplied mock unchanged, adding a durable snapshot around its responses."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
from http.server import HTTPServer

ROOT = Path(__file__).resolve().parents[1]


# Import the exercise server without executing its command-line entrypoint.
def load_mock():
    """Import the exercise server without executing its command-line entrypoint."""
    specification = importlib.util.spec_from_file_location(
        "exercise_mock", ROOT / "exercise-pack/starter-kit/mock-apis/mock_server.py"
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


# Convert tuple-keyed inventory into a lossless JSON-compatible representation.
def snapshot_state(state):
    """Convert tuple-keyed inventory into a lossless JSON-compatible representation."""
    return {**state, "inventory": list(state["inventory"].values())}


# Rehydrate numeric order IDs and tuple inventory keys after restart.
def restore_state(snapshot):
    """Rehydrate numeric order IDs and tuple inventory keys after restart."""
    snapshot["inventory"] = {
        (row["inventory_item_id"], row["location_id"]): row
        for row in snapshot["inventory"]
    }
    snapshot["orders"] = {int(key): value for key, value in snapshot["orders"].items()}
    return snapshot


# Persist mock side effects before their HTTP response, preserving uncertain outcomes.
def serve(host, port, snapshot_path):
    """Persist mock side effects before their HTTP response, preserving uncertain outcomes."""
    module = load_mock()
    module.FLAKE = False
    destination = Path(snapshot_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        module.S = restore_state(json.loads(destination.read_text(encoding="utf-8")))
    module.VARIANTS = {
        variant["id"]: variant
        for product in module.S["products"]
        for variant in product["variants"]
    }

    class DurableHandler(module.H):
        """Persist mutations without changing the exercise's API or behavior."""

        # Atomically snapshot the mock before acknowledging a mutating request.
        def _send(self, code, body, extra=None):
            """Atomically snapshot the mock before acknowledging a mutating request."""
            if self.command == "POST":
                temporary = destination.with_suffix(".pending")
                with temporary.open("w", encoding="utf-8") as handle:
                    json.dump(snapshot_state(module.S), handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary.replace(destination)
            return super()._send(code, body, extra)

    server = HTTPServer((host, port), DurableHandler)
    print(f"Persistent mock on http://{host}:{port}", flush=True)
    server.serve_forever()


# Accept a local bind address and a snapshot location from the demo runner.
def main():
    """Accept a local bind address and a snapshot location from the demo runner."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--snapshot", default="runtime/mock-state.json")
    arguments = parser.parse_args()
    serve(arguments.host, arguments.port, arguments.snapshot)


if __name__ == "__main__":
    main()
