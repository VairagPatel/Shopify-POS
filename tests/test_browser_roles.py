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
from test_phone_privacy import private_source


# Run an isolated HTTP app so browser tests cannot modify the reviewer's open demo.
def test_browser_roles_and_multi_frame_sale(production_env, private_source, monkeypatch):
    _, store, _, _ = production_env
    source, source_log = private_source
    monkeypatch.setenv('ELUNO_PRIVATE_LOOKUP', '1')
    monkeypatch.setenv('ELUNO_MOCK_URL', str(source.client.base_url))
    from app.operations import founder_digest, enqueue_email

    founder_digest(store, source, "2026-10-06")
    enqueue_email(
        store,
        "variance-browser",
        "Cash variance · HSR",
        "Drawer variance: INR -250.00. Counted: INR 10450.00.",
    )
    with store._connect() as connection:
        connection.execute(
            "UPDATE outbox SET status='delivery_uncertain',error=? WHERE id='variance-browser'",
            ("SMTP response lost <script>window.outboxInjected=true</script>",),
        )
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
                request_urls=[]
                page.on("request", lambda request: request_urls.append(request.url))
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
                        "9000000004"
                    )
                    page.get_by_role("button", name="Add wearer").click()
                    page.wait_for_function(
                        "!state.busy && state.cart.members.length===1"
                    )
                    for identifier in [91000003, 91000005]:
                        page.locator('[data-category="frame"]').click()
                        page.wait_for_function("!state.busy")
                        page.locator(f'[data-product="{identifier}"]').click()
                        page.locator('[data-action="add-configured-pair"]').wait_for()
                        page.locator('[data-action="add-configured-pair"]').click()
                        page.wait_for_function("!state.busy")
                    assert len(page.evaluate("state.cart.members[0].variant_ids")) == 4
                    page.locator('[data-remove-pair="0"]').click()
                    page.wait_for_function("!state.busy")
                    remaining_pair = page.evaluate("state.cart.members[0].variant_ids")
                    assert len(remaining_pair) == 2 and remaining_pair[0] == 91000005
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
                for view in ["overview", "transactions", "clinical", "till", "evidence"] + (["audit"] if role in {"admin", "finance"} else []):
                    page.locator(f'.nav-button[data-page="{view}"]').click()
                    page.wait_for_function("!state.busy")
                    assert "We couldn't load this view" not in page.locator("#main").inner_text()
                    if view=="clinical" and role in {"admin","optometrist"}:
                        assert page.locator('select[name="od_axis"] option[value="0"]').count()==1
                page.locator('[data-page="reports"]').click()
                page.get_by_role("heading", name="Total daily performance").wait_for()
                page.wait_for_function("!state.busy")
                with page.expect_response(
                    lambda response: "/api/reports?day=2026-10-06" in response.url
                ) as report_response:
                    page.locator("#report-date").fill("2026-10-06")
                report = report_response.value.json()
                page.wait_for_function(
                    "document.querySelector('.page-heading').innerText.includes('2026-10-06')"
                )
                expected_stores = 7 if role in {"admin", "finance"} else 1
                assert len(report["stores"]) == expected_stores
                assert (
                    page.locator("#store-breakdown tbody tr").count() == expected_stores
                )
                assert not page.locator("#store-breakdown").evaluate(
                    "(element)=>element.open"
                )
                sales = sum(item["sales_paise"] for item in report["stores"])
                bills = sum(item["bill_count"] for item in report["stores"])
                net = sum(item["net_collected_paise"] for item in report["stores"])
                average = (sales * 2 + bills) // (bills * 2) if bills else 0
                for metric, value in [
                    ("sales", sales),
                    ("net", net),
                    ("average", average),
                ]:
                    expected = page.evaluate("(value)=>money(value)", value)
                    assert (
                        page.locator(f'[data-report="{metric}"]').inner_text()
                        == expected
                    )
                assert page.locator('[data-report="bills"]').inner_text() == str(bills)
                if role in {"admin", "finance"}:
                    assert page.locator("#store-select").count() == 0
                    page.screenshot(
                        path="runtime/screenshots/leadership-daily-report.png",
                        full_page=True,
                    )
                if role == "finance":
                    with page.expect_response(
                        lambda response: "/api/reports?day=2000-01-01" in response.url
                    ):
                        page.locator("#report-date").fill("2000-01-01")
                    page.get_by_text(
                        "No sales recorded for this date.", exact=False
                    ).wait_for()
                    assert page.locator('[data-report="bills"]').inner_text() == "0"
                    assert page.locator(
                        '[data-report="average"]'
                    ).inner_text() == page.evaluate("money(0)")
                if role in {"admin", "finance"}:
                    page.wait_for_function("!state.busy")
                    page.locator('[data-page="outbox"]').click()
                    page.get_by_role(
                        "heading", name="Report outbox", exact=True
                    ).wait_for()
                    digest = page.locator('[data-message-id="digest-2026-10-06"]')
                    assert digest.locator("tbody tr").count() == 7
                    assert "IST" in digest.locator(".outbox-meta").inner_text()
                    assert digest.locator(".outbox-original").evaluate(
                        "(element)=>!element.open"
                    )
                    alert = page.locator('[data-message-id="variance-browser"]')
                    assert "Delivery uncertain" in alert.inner_text()
                    assert (
                        "SMTP response lost <script>"
                        in alert.locator(".outbox-error").inner_text()
                    )
                    assert page.evaluate("window.outboxInjected === undefined")
                    page.screenshot(
                        path="runtime/screenshots/report-outbox.png", full_page=True
                    )
                assert not any("phone=" in url or "9000000005" in url for url in request_urls)
                context.close()
            assert not errors, errors
            assert '9000000005' not in source_log.read_text(encoding='utf-8')
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
