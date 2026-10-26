"""Exercise coupon selection, pricing, clearing, payment and refund in real Chrome."""

import os
import socket
import subprocess
import sys
import time
import httpx
import pytest
from playwright.sync_api import sync_playwright
from test_production_matrix import production_env, identity_template, backend
from test_phone_privacy import private_source


# Keep browser writes and source inventory isolated from the user's running demo.
@pytest.fixture
def coupon_app(production_env, private_source, monkeypatch):
    clients, store, _, _ = production_env
    source, _ = private_source
    monkeypatch.setenv("ELUNO_PRIVATE_LOOKUP", "1")
    monkeypatch.setenv("ELUNO_MOCK_URL", str(source.client.base_url))
    from datetime import datetime, timedelta
    from app.constants import INDIA
    clinical=clients('optometrist').post('/api/prescriptions',json={
        'phone':'9000000005','valid_until':(datetime.now(INDIA).date()+timedelta(days=365)).isoformat(),
        'od':{'sph':-3.25,'cyl':0,'axis':0,'add':2.5},
        'os':{'sph':-3.5,'cyl':0,'axis':0,'add':2.5},
    })
    assert clinical.status_code==200,clinical.text
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        env=os.environ.copy(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(base + "/health", timeout=1, trust_env=False).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            raise AssertionError("Isolated coupon app did not start")
        yield base, store, source
    finally:
        process.terminate()
        process.wait(timeout=10)


# Use the visible frame and lens configurator rather than injecting cart state.
def add_pair(page, frame_id, coating="blue_cut"):
    page.locator('[data-category="frame"]').click()
    page.wait_for_function("!state.busy")
    page.locator(f'[data-product="{frame_id}"]').click()
    page.locator("#lens-type").select_option("progressive")
    page.wait_for_function("!state.busy")
    page.locator("#lens-index").select_option("1.6")
    page.wait_for_function("!state.busy")
    page.locator("#lens-coating").select_option(coating)
    page.wait_for_function("!state.busy")
    page.locator('[data-action="add-configured-pair"]').click()
    page.wait_for_function("!state.busy && !document.querySelector('#modal').open")


# Confirm the request, its exact discount, and the amount displayed to the cashier.
def apply_coupon(page, code, discount, gross):
    page.locator("#offer-code").select_option(code)
    page.wait_for_function("!state.busy")
    assert page.locator("#offer-code").input_value() == code
    with page.expect_response(lambda response: response.url.endswith("/sales/prepare")) as pending:
        page.locator('[data-action="apply-coupon"]').click()
    response = pending.value
    quote = response.json()
    assert response.status == 200, quote
    page.wait_for_function("!state.busy && state.quote !== null")
    applied = [offer for offer in quote["offers"] if offer["applied"]]
    assert len(applied) == 1 and applied[0]["offer_id"] == code
    assert applied[0]["amount_paise"] == discount
    assert quote["total_paise"] == gross - discount
    assert page.locator("#bill-panel .total").inner_text() == page.evaluate("money(state.quote.total_paise)")
    assert code in page.locator("#coupon-status").inner_text()
    return quote


# Run every currently eligible seed coupon, then prove the saved source order and refund.
def test_coupons_from_dropdown_to_shopify_and_refund(coupon_app):
    base, store, source = coupon_app
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.environ.get("ELUNO_BROWSER_CHANNEL", "chrome") or None, headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base)
            page.locator("input[name=username]").fill("manager")
            page.locator("input[name=password]").fill("Acceptance-password-2026!")
            page.get_by_role("button", name="Sign in to Store Studio").click()
            page.locator('[data-page="billing"]').wait_for()
            page.locator('[data-page="billing"]').click()
            page.locator("#customer-form input[name=phone]").fill("9000000005")
            page.get_by_role("button", name="Add wearer").click()
            page.wait_for_function("!state.busy && state.cart.members.length === 1")
            add_pair(page, 91000003)
            assert page.locator("#offer-code").input_value() == ""
            codes = page.locator("#offer-code option").evaluate_all("options=>options.map(option=>option.value)")
            assert "MONSOON20" not in codes and "SECONDPAIR50" not in codes
            gross = 2049700  # ₹10,998 frame + ₹9,499 lens pair.
            for code, amount in [
                ("FESTIVE10", 109980), ("PRIORITY500", 50000),
                ("PGX_CAMPAIGN15", 142485), ("FREE_BLUECUT_PGX", 100000), ("BUNDLE300", 30000),
            ]:
                apply_coupon(page, code, amount, gross)
                print(f"COUPON QC {code}: gross={gross} discount={amount} total={gross-amount}")

            # A saved legacy quote must not restore a discount when no coupon was selected.
            page.evaluate("""() => {
                const key='eluno-cart-'+state.user.username;
                const saved=JSON.parse(localStorage.getItem(key));
                saved.offer_id='';localStorage.setItem(key,JSON.stringify(saved));
            }""")
            page.reload()
            page.locator('.nav-button[data-page="billing"]').wait_for()
            page.locator('.nav-button[data-page="billing"]').click()
            page.wait_for_function("!state.busy")
            assert page.evaluate("state.quote") is None
            # Clearing the coupon returns to full MRP; no other eligible offer takes over.
            page.locator("#offer-code").select_option("")
            page.wait_for_function("!state.busy")
            with page.expect_response(lambda response: response.url.endswith("/sales/prepare")) as pending:
                page.locator('[data-action="prepare-sale"]').click()
            no_coupon = pending.value.json()
            assert no_coupon["total_paise"] == gross
            assert not any(offer["applied"] for offer in no_coupon["offers"])
            page.wait_for_function("!state.busy")

            # A manager percentage without a reason also leaves the bill undiscounted.
            page.locator('details:has(#override-percent)').evaluate("element=>element.open=true")
            page.locator("#override-percent").fill("5")
            page.locator("#override-percent").press("Tab")
            page.wait_for_function("!state.busy")
            with page.expect_response(lambda response: response.url.endswith("/sales/prepare")) as pending:
                page.locator('[data-action="prepare-sale"]').click()
            assert pending.value.json()["total_paise"] == gross
            page.wait_for_function("!state.busy")
            page.locator('details:has(#override-percent)').evaluate("element=>element.open=true")
            page.locator("#discount-reason").select_option("walk_out_retention")
            page.wait_for_function("!state.busy")
            with page.expect_response(lambda response: response.url.endswith("/sales/prepare")) as pending:
                page.locator('[data-action="prepare-sale"]').click()
            manager_quote = pending.value.json()
            assert manager_quote["total_paise"] == gross - 102485
            page.wait_for_function("!state.busy")

            # Selecting a coupon clears the manager override and applies only that coupon.
            apply_coupon(page, "FESTIVE10", 109980, gross)
            assert page.evaluate("state.cart.override_percent") == ""
            add_pair(page, 91000005, "photochromic")
            quote = apply_coupon(page, "SECONDPAIR50", 474950, 3999400)
            identifier = quote["checkout_id"]
            page.locator('[data-action="complete-sale"]').click()
            page.locator("dialog[open] .receipt").wait_for()
            page.wait_for_function("!state.busy")
            checkout = store.get_checkout(identifier)
            order = source.order_by_id(checkout["shopify_order_id"])
            from app.domain.money import paise
            assert paise(order["total_price"]) == quote["total_paise"]
            assert sum(paise(line["total_discount"]) for line in order["line_items"]) == 474950
            page.locator('[data-action="refund-dialog"]').click()
            page.locator('#refund-form textarea[name="reason"]').fill("Coupon QC full return")
            page.locator("#refund-form button").click()
            page.wait_for_function("!state.busy")
            page.locator('[data-action="complete-refund"]').click()
            page.wait_for_function("!state.busy && state.detail.refunds[0].status === 'recorded'")
            refunded = source.order_by_id(checkout["shopify_order_id"])
            assert sum(paise(transaction["amount"]) for refund in refunded["refunds"] for transaction in refund["transactions"]) == quote["total_paise"]
            assert not errors, errors
        finally:
            browser.close()
