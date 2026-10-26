# Cashier multi-item acceptance walkthrough

Use synthetic customers and the supplied source mock. The frontend and Swagger use the same authenticated APIs and persisted quotes.

## Browser

1. Sign in as cashier; open **New sale** and add customer `+919000000005`.
2. In **Frames**, select two different in-stock frames and configure one lens pair for each. Both pairs must remain on the bill.
3. In **Lens only**, configure and add a prescription lens pair without a frame. It must appear as its own cart line and pass the wearer's prescription validation.
4. Select one eligible coupon. Only that coupon should apply; offers requiring a frame/lens bundle must not apply to a lens-only line.
5. Remove a frame pair and a lens-only line separately. Each removal must update the draft and re-evaluate eligible coupons.
6. Reload and return to New sale. Saved frame pairs and lens-only pairs must remain.
7. Select **Review offers & GST**. Review the exact total and then confirm the payment.
8. Check the receipt and technical evidence: one checkout, one source order, all selected lines, tax and discount totals, correct store and payment reference.
9. As manager, return the bill. Check the credit note and source refund; frames return to the original store's stock. Lenses are not restocked.
10. Try to add more frame units than available across all wearers. The screen must reject the increment; the API independently rejects excessive demand.

Within each wearer, the first frame pairs with the first lens, the second frame with the second lens, and so on. Remaining units are standalone. Each lens uses that wearer's prescription. This demo uses up to ten wearers and thirty units per wearer. Quote/source lines retain one line per unit so discount, tax and refund allocations remain exact.

Lens-only variants are supplied as `lens_only_variant_ids` in a wearer selection. One variant represents a prescription lens pair. The Shopify line carries the wearer's prescription and has no frame pair reference.

## Swagger

1. Open `/docs`, execute `POST /auth/login` with locally provisioned cashier credentials. The custom Swagger page supplies the session CSRF token for subsequent writes.
2. Use `GET /api/bootstrap` and `GET /api/inventory?store_code=HSR` to select available variant IDs.
3. Execute `POST /sales/prepare` with the following body (adjust staff/store to your signed-in account):

```json
{
  "phone": "+919000000005",
  "store_code": "HSR",
  "staff_id": "S105",
  "variant_ids": [],
  "members": [
    {"phone": "+919000000005", "variant_ids": [91000003, 91000005]}
  ],
  "payment_method": "upi",
  "channel": "walk_in"
}
```

4. Repeat a variant ID inside a wearer's `variant_ids` to request another unit, subject to stock.
5. To sell a lens pair without a frame, use `variant_ids: []` and `lens_only_variant_ids: [91000083]` for the wearer. The lens still requires a current compatible prescription.
6. Inspect `GET /api/checkouts/{identifier}/detail` before completing. It must contain the saved quote and no recorded source order yet.
7. Execute `POST /sales/{checkout_id}/complete`, then fetch detail again. Inspect the source order, transactions, line items and invoice.
8. Execute completion again: the same order ID must return without another charge or stock decrement.
9. Sign in as manager to run `POST /refunds/prepare` then `POST /refunds/{refund_id}/complete`. Inspect original order evidence and credit-note data.

Existing flat `variant_ids` requests retain their original distinct-variant, balanced-pair contract. Use `members` for multi-frame, quantity and family carts; existing endpoints and saved data remain compatible.

## Automated execution

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The browser test defaults to installed Google Chrome and requires permission to launch local processes. Alternatively install Playwright Chromium and set `ELUNO_BROWSER_CHANNEL` to an empty string (as in GitHub Actions). Tests use temporary application databases and fresh mock processes; they do not change the open demo. A synthetic invoice screenshot is saved to ignored `runtime/screenshots/production-cashier.png`.

For backend-only execution: `python -m pytest --ignore=tests/test_browser_roles.py -q`. The complete run must also include the browser test before claiming UI verification.
