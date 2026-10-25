"""Browser acceptance for family billing, remakes, cash, clinical entry and permissions."""

from pathlib import Path
from datetime import date, timedelta
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


# Exercise additional stakeholder workflows through actual visible controls.
def main():
    """Create synthetic acceptance records and verify their persisted browser outcomes."""
    credentials = {
        line.split("\t")[0]: line.split("\t")[1]
        for line in (ROOT / "runtime/demo-accounts.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    }
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8001")
        page.locator("input[name=username]").fill("admin")
        page.locator("input[name=password]").fill(credentials["admin"])
        page.get_by_role("button", name="Sign in to Store Studio").click()
        page.wait_for_function("!state.busy")
        page.get_by_role("button", name="Start guided sale").click()
        page.wait_for_function("!state.busy")
        for phone, frame in [("+919000000004", 91000005), ("+919000000007", 91000006)]:
            page.locator("#customer-form input[name=phone]").fill(phone)
            page.get_by_role("button", name="Add wearer").click()
            page.wait_for_function("!state.busy")
            frame = page.evaluate(
                "state.data.catalog.find(item => item.eluno.line_type === 'frame' && item.eluno.rx_able && item.eluno.category !== 'sunglasses' && state.stock[item.inventory_item_id] > 0 && !state.cart.members.some(member => member.variant_ids.includes(item.id))).id"
            )
            page.locator(f'[data-product="{frame}"]').wait_for()
            page.locator(f'[data-product="{frame}"]').click()
            page.wait_for_function("!state.busy")
            page.locator('[data-category="lens"]').click()
            page.wait_for_function("!state.busy")
            page.locator('[data-product="91000083"]').click()
            page.wait_for_function("!state.busy")
            page.locator('[data-category="frame"]').click()
            page.wait_for_function("!state.busy")
        page.get_by_role("button", name="Review offers & GST").click()
        page.wait_for_function("!state.busy")
        page.get_by_role("button", name="Confirm UPI", exact=False).click()
        page.wait_for_function("!state.busy")
        page.locator("dialog[open] .receipt tbody tr").first.wait_for()
        assert page.locator("dialog[open] .receipt tbody tr").count() == 6
        page.screenshot(path=str(ROOT / "runtime/screenshots/family-invoice.png"))
        page.get_by_role("button", name="Remake lens", exact=True).click()
        page.wait_for_function("!state.busy")
        page.locator("select[name=lens_variant_id]").select_option("91000083")
        page.locator("input[name=lab_cost]").fill("1200")
        page.locator("textarea[name=reason]").fill(
            "Browser progressive adaptation test"
        )
        page.get_by_role("button", name="Prepare remake", exact=True).click()
        page.wait_for_function("!state.busy")
        page.get_by_role("button", name="Confirm payment", exact=True).click()
        page.wait_for_function("!state.busy")
        page.locator("dialog[open]").get_by_text(
            "order recorded", exact=True
        ).wait_for()
        assert page.locator("dialog[open] .receipt tbody tr").count() == 1
        page.get_by_role("button", name="Close ✕", exact=True).click()
        page.locator('[data-page="till"]').click()
        page.wait_for_function("!state.busy")
        if page.locator("#open-till-form").count():
            page.locator("#open-till-form input[name=amount]").fill("2000")
            page.get_by_role("button", name="Open drawer", exact=True).click()
            page.wait_for_function("!state.busy")
        page.locator("#expense-form input[name=amount]").fill("50")
        page.locator("#expense-form input[name=reason]").fill("Browser courier test")
        page.get_by_role("button", name="Record cash out").click()
        page.wait_for_function("!state.busy")
        expected = page.evaluate("state.till.expected_paise")
        page.locator("#close-till-form input[name=amount]").fill(
            str((expected - 25000) / 100)
        )
        page.get_by_role("button", name="Reconcile & close drawer").click()
        page.wait_for_function("!state.busy")
        page.get_by_role("heading", name="Start with your opening float.").wait_for()
        page.locator('[data-page="outbox"]').click()
        page.wait_for_function("!state.busy")
        page.get_by_role("heading", name="Cash variance · HSR").first.wait_for()
        page.screenshot(path=str(ROOT / "runtime/screenshots/outbox.png"))
        page.locator('[data-page="clinical"]').click()
        page.wait_for_function("!state.busy")
        page.locator("#rx-form input[name=phone]").fill("+919000000005")
        page.locator("#rx-form input[name=valid_until]").fill(
            (date.today() + timedelta(days=180)).isoformat()
        )
        assert page.locator("select[name=od_axis] option").count() == 37
        page.locator("input[name=od_sph]").fill("-3.25")
        page.locator("input[name=os_sph]").fill("-3")
        page.locator("input[name=od_add]").fill("2.5")
        page.locator("input[name=os_add]").fill("2.5")
        page.get_by_role("button", name="Save prescription", exact=True).click()
        page.wait_for_function("!state.busy")
        page.get_by_text(
            "Prescription recorded with your clinical identity.", exact=True
        ).wait_for()
        page.get_by_role("button", name="Sign out", exact=True).click()
        page.wait_for_function("!state.busy")
        page.locator("input[name=username]").fill("cashier")
        page.locator("input[name=password]").fill(credentials["cashier"])
        page.get_by_role("button", name="Sign in to Store Studio").click()
        page.wait_for_function("!state.busy")
        page.get_by_role("button", name="Start guided sale").click()
        page.wait_for_function("!state.busy")
        assert page.get_by_text("Manager discount", exact=True).count() == 0
        assert page.locator('[data-page="audit"]').count() == 0
        assert page.locator('[data-page="outbox"]').count() == 0
        assert not errors, errors
        browser.close()
    print(
        "Extended Chrome acceptance passed: three-wearer invoice, zero-charge remake, cash expense/variance outbox, Rx entry, cashier restrictions; no page errors."
    )


if __name__ == "__main__":
    main()
