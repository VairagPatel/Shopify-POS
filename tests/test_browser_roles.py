"""Real Chrome role navigation and cashier cart-to-source acceptance checks."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
from test_production_matrix import production_env, identity_template, backend


# Run an isolated HTTP app so browser tests cannot modify the reviewer's open demo.
def test_browser_roles_and_multi_frame_sale(production_env):
    _, store, source, _ = production_env
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    errors = []
    try:
        for _ in range(100):
            try:
                if httpx.get(base + "/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            raise AssertionError("Isolated app did not start")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel=os.environ.get("ELUNO_BROWSER_CHANNEL", "chrome") or None,
                headless=True,
            )
            for role in ["cashier", "manager", "optometrist", "finance", "admin"]:
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                page.locator("input[name=username]").fill(role)
                page.locator("input[name=password]").fill("Acceptance-password-2026!")
                page.get_by_role("button", name="Sign in to Store Studio").click()
                page.locator('[data-page="reports"]').wait_for()
                page.wait_for_function("!state.busy")
                assert page.locator('[data-page="billing"]').count() == (
                    1 if role in {"cashier", "manager", "admin"} else 0
                )
                assert page.locator('[data-page="audit"]').count() == (
                    1 if role in {"finance", "admin"} else 0
                )
                if role == "cashier":
                    page.locator('[data-page="billing"]').click()
                    page.locator("#customer-form input[name=phone]").fill(
                        "+919000000005"
                    )
                    page.get_by_role("button", name="Add wearer").click()
                    page.wait_for_function(
                        "!state.busy && state.cart.members.length===1"
                    )
                    for identifier in [91000003, 91000005, 91000003]:
                        page.locator(f'[data-product="{identifier}"]').click()
                        page.wait_for_function("!state.busy")
                    assert page.evaluate("state.cart.members[0].variant_ids") == [
                        91000003,
                        91000005,
                        91000003,
                    ]
                    page.locator(
                        '[data-quantity="-1"][data-variant="91000003"]'
                    ).click()
                    page.wait_for_function("!state.busy")
                    assert page.evaluate("state.cart.members[0].variant_ids") == [
                        91000005,
                        91000003,
                    ]
                    page.reload()
                    page.locator('[data-page="billing"]').click()
                    page.wait_for_function("!state.busy")
                    assert len(page.evaluate("state.cart.members[0].variant_ids")) == 2
                    page.get_by_role("button", name="Review offers & GST").click()
                    page.get_by_role(
                        "button", name="Confirm UPI", exact=False
                    ).wait_for()
                    identifier = page.evaluate("state.quote.checkout_id")
                    page.get_by_role("button", name="Confirm UPI", exact=False).click()
                    page.locator("dialog[open] .receipt").wait_for()
                    recorded = store.get_checkout(identifier)
                    order = source.order_by_id(recorded["shopify_order_id"])
                    assert len(order["line_items"]) == 2
                    screenshot = Path("runtime/screenshots/production-cashier.png")
                    screenshot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(screenshot), full_page=True)
                    page.get_by_role("button", name="Close ✕", exact=True).click()
                    page.wait_for_function("!state.busy")
                page.locator('[data-page="reports"]').click()
                page.get_by_role("heading", name="Store performance").wait_for()
                context.close()
            assert not errors, errors
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
