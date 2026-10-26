"""Exercise the real browser UI using local, gitignored reviewer credentials."""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


# Verify the rendered login-to-sale-to-refund journey and save visual evidence.
def main():
    """Verify the rendered login-to-sale-to-refund journey and save visual evidence."""
    credentials = (
        (ROOT / "runtime/demo-accounts.txt").read_text(encoding="utf-8").splitlines()
    )
    password = next(
        line.split("\t")[1] for line in credentials if line.startswith("admin\t")
    )
    screenshots = ROOT / "runtime/screenshots"
    screenshots.mkdir(exist_ok=True)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(
            viewport={"width": 1440, "height": 1050}, device_scale_factor=1
        )
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8001")
        page.locator("input[name=username]").fill("admin")
        page.locator("input[name=password]").fill(password)
        page.get_by_role("button", name="Sign in to Store Studio").click()
        page.get_by_role("heading", name="Good to see you, Demo.").wait_for()
        page.screenshot(path=str(screenshots / "overview.png"), full_page=True)
        page.get_by_role("button", name="Start guided sale").click()
        page.get_by_role("button", name="Review offers & GST").wait_for()
        page.screenshot(path=str(screenshots / "billing.png"), full_page=True)
        page.get_by_role("button", name="Review offers & GST").click()
        page.get_by_role("button", name="Confirm UPI", exact=False).wait_for()
        page.screenshot(path=str(screenshots / "quote.png"), full_page=True)
        page.get_by_role("button", name="Confirm UPI", exact=False).click()
        page.locator("dialog[open] .receipt").wait_for()
        page.locator("dialog[open]").get_by_text(
            "order recorded", exact=True
        ).wait_for()
        page.screenshot(path=str(screenshots / "invoice.png"), full_page=True)
        page.get_by_role("button", name="Full refund", exact=True).click()
        page.locator("textarea[name=reason]").fill("Browser acceptance return")
        page.get_by_role("button", name="Preview refund amount").click()
        page.get_by_role("button", name="Confirm refund", exact=True).click()
        page.get_by_role("button", name="Credit note", exact=True).wait_for()
        page.get_by_role("button", name="Credit note", exact=True).click()
        page.get_by_role("heading", name="Credit note", exact=True).wait_for()
        page.screenshot(path=str(screenshots / "credit-note.png"), full_page=True)
        page.get_by_role("button", name="Close ✕", exact=True).click()
        page.locator('[data-page="reports"]').click()
        page.get_by_role("heading", name="Total daily performance").wait_for()
        page.screenshot(path=str(screenshots / "reports.png"), full_page=True)
        page.locator('[data-page="evidence"]').click()
        page.get_by_role("heading", name="Stakeholder acceptance map").wait_for()
        page.screenshot(path=str(screenshots / "coverage.png"), full_page=True)
        assert not errors, errors
        browser.close()
    print(
        json.dumps(
            {
                "browser": "Chrome",
                "result": "passed",
                "screenshots": str(screenshots),
                "page_errors": errors,
            }
        )
    )


if __name__ == "__main__":
    main()
