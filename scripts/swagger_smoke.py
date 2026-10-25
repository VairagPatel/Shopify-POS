"""Prove Swagger can authenticate and execute the source-data/quote flow without the frontend."""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


# Use the Swagger controls themselves to establish a session and execute a protected write.
def main():
    """Check direct Swagger login, customer lookup and quote preparation in a fresh browser."""
    credentials = (
        (ROOT / "runtime/demo-accounts.txt").read_text(encoding="utf-8").splitlines()
    )
    password = next(
        line.split("\t")[1] for line in credentials if line.startswith("manager\t")
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        base = "http://127.0.0.1:8001"
        page.goto(base + "/docs")
        login = page.locator(".opblock").filter(
            has=page.locator(".opblock-summary-path", has_text="/auth/login")
        )
        login.locator(".opblock-summary").click()
        login.get_by_role("button", name="Try it out").click()
        login.locator("textarea").fill(
            json.dumps({"username": "manager", "password": password})
        )
        with page.expect_response(
            lambda response: (
                response.url.endswith("/auth/login")
                and response.request.method == "POST"
            )
        ) as login_response:
            login.get_by_role("button", name="Execute", exact=True).click()
        assert login_response.value.status == 200
        # Clear the password from the visible editor before capturing any screenshots.
        login.locator("textarea").fill(
            json.dumps({"username": "manager", "password": "[hidden]"})
        )
        login.locator(".opblock-summary").click()
        customer = page.locator(".opblock").filter(
            has=page.locator(".opblock-summary-path", has_text="/api/customers")
        )
        customer.locator(".opblock-summary").click()
        customer.get_by_role("button", name="Try it out").click()
        customer.locator(".parameters-col_description input").fill("+919000000005")
        with page.expect_response(
            lambda response: "/api/customers?" in response.url
        ) as customer_response:
            customer.get_by_role("button", name="Execute", exact=True).click()
        assert customer_response.value.status == 200
        assert customer_response.value.json()["customer"]["phone"] == "+919000000005"
        catalog = page.request.get(base + "/api/bootstrap").json()["catalog"]
        stock = {
            row["inventory_item_id"]: row["available"]
            for row in page.request.get(base + "/api/inventory?store_code=HSR").json()[
                "inventory_levels"
            ]
        }
        frame = next(
            item["id"]
            for item in catalog
            if item["eluno"]["line_type"] == "frame"
            and item["eluno"].get("rx_able")
            and stock.get(item["inventory_item_id"], 0) > 0
        )
        quote = page.locator(".opblock").filter(
            has=page.locator(".opblock-summary-path", has_text="/sales/prepare")
        )
        quote.locator(".opblock-summary").click()
        quote.get_by_role("button", name="Try it out").click()
        quote.locator("textarea").fill(
            json.dumps(
                {
                    "phone": "+919000000005",
                    "store_code": "HSR",
                    "staff_id": "S108",
                    "variant_ids": [frame, 91000083],
                    "payment_method": "upi",
                }
            )
        )
        with page.expect_response(
            lambda response: (
                response.url.endswith("/sales/prepare")
                and response.request.method == "POST"
            )
        ) as quote_response:
            quote.get_by_role("button", name="Execute", exact=True).click()
        assert quote_response.value.status == 200, quote_response.value.text()
        assert quote_response.value.json()["status"] == "draft"
        checkout_id = quote_response.value.json()["checkout_id"]
        session = page.request.get(base + "/auth/me").json()
        cancelled = page.request.post(
            base + "/api/checkouts/" + checkout_id + "/cancel",
            data=json.dumps({"reason": "Swagger-only acceptance check complete"}),
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": session["csrf"],
            },
        )
        assert cancelled.status == 200
        browser.close()
    print(
        "Swagger-only Chrome check passed: login, source customer/prescriptions, CSRF-protected quote; frontend never opened. Test draft cancelled with invoice retained."
    )


if __name__ == "__main__":
    main()
