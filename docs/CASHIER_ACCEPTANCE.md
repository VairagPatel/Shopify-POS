# Cashier multi-item acceptance walkthrough

Use synthetic customers and the supplied source mock. The frontend and Swagger use the same authenticated APIs and persisted quotes.

## Browser

1. Sign in as cashier; open **New sale** and add customer `+919000000005`.
2. Select two different in-stock frames. Both must remain on the bill.
3. Click a selected product again, or its **+** control. Quantity and MRP must increase. Use **−** to remove one unit; removing the final unit removes that row.
4. Reload and return to New sale. The saved items and quantities must remain.
5. Select **Review offers & GST**. Review the exact total and then confirm the payment.
6. Check the receipt and technical evidence: one checkout, one source order, all selected units, tax and discount totals, correct store and payment reference.
7. As manager, return the bill. Check the credit note and source refund; frames return to the original store's stock. Lenses are not restocked.
8. Try to add more units than available across all wearers. The screen must reject the increment; the API independently rejects excessive demand.

Within each wearer, the first frame pairs with the first lens, the second frame with the second lens, and so on. Remaining units are standalone. Each lens uses that wearer's prescription. This demo uses up to ten wearers and thirty units per wearer. Quote/source lines retain one line per unit so discount, tax and refund allocations remain exact.

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
5. Inspect `GET /api/checkouts/{identifier}/detail` before completing. It must contain the saved quote and no recorded source order yet.
6. Execute `POST /sales/{checkout_id}/complete`, then fetch detail again. Inspect the source order, transactions, line items and invoice.
7. Execute completion again: the same order ID must return without another charge or stock decrement.
8. Sign in as manager to run `POST /refunds/prepare` then `POST /refunds/{refund_id}/complete`. Inspect original order evidence and credit-note data.

Existing flat `variant_ids` requests retain their original distinct-variant, balanced-pair contract. Use `members` for multi-frame, quantity and family carts; existing endpoints and saved data remain compatible.

## Automated execution

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The browser test defaults to installed Google Chrome and requires permission to launch local processes. Alternatively install Playwright Chromium and set `ELUNO_BROWSER_CHANNEL` to an empty string (as in GitHub Actions). Tests use temporary application databases and fresh mock processes; they do not change the open demo. A synthetic invoice screenshot is saved to ignored `runtime/screenshots/production-cashier.png`.

For backend-only execution: `python -m pytest --ignore=tests/test_browser_roles.py -q`. The complete run must also include the browser test before claiming UI verification.
