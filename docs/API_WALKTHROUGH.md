# Explain the full flow using Swagger or the frontend

Both interfaces use the **same backend, same business rules and same records**. The frontend is a convenient client; it is not required to demonstrate the implementation.

| Demo mode | Entry point | What to emphasize |
|---|---|---|
| Frontend | `/` | Staff workflow, validation feedback, bill, receipt and reports |
| Swagger | `/docs` | Input schemas, source reads, calculated quote, writes, returned IDs and recovery states |

The current local review URL is `http://127.0.0.1:8001`; the normal runner default is port 8000. Always use `/` and `/docs` on the **same port**. The old API-only process on another port may have a different database.

## Where each piece of data comes from

| Data | Source | App behavior |
|---|---|---|
| Customer identity and priority/campaign tags | Shopify mock customer lookup | Read existing customer; no customer creation in this demo |
| Products, variant IDs, selling prices and HSN metadata | Shopify mock catalog | Read; do not trust a price supplied by the browser |
| Store location and tracked stock | Shopify mock | Read before quoting; source order creation decrements physical stock |
| Staff authorization and issued prescriptions | SMT/store-tool mock | Read and validate |
| Newly entered prescriptions | Local clinical overlay | Added by an authenticated optometrist; merged into issued records for validation |
| Offer rules and effective-date GST rates | Supplied local JSON configuration | Calculated by app services, not fetched as Shopify discount rules |
| Payment capture/refund | Terminal mock, or local cash handling | Separate from creating the Shopify order/refund |
| Quote, invoice sequence, operation status and external references | Local SQLite | Durable recovery and audit; not the source sales ledger |
| Orders and source refunds | Shopify mock | Write, then read back for evidence and reporting |

The customer directory in bootstrap is a local synthetic search aid. The actual selected customer is fetched through the Shopify lookup. A catalog variant ID, an inventory item ID and a Shopify order ID are different identifiers.

## Sale sequence

```mermaid
sequenceDiagram
    actor Reviewer
    participant Client as Frontend or Swagger
    participant API as FastAPI services
    participant Shopify as Shopify mock
    participant SMT as Store-tool mock
    participant DB as SQLite
    participant Terminal as Terminal mock
    Reviewer->>Client: Select customer, wearer items, store and payment method
    Client->>API: POST /sales/prepare
    API->>Shopify: Read customer, variants, location and stock
    API->>SMT: Read staff and wearer prescriptions
    Note over API: Validate each Rx; apply local offer and GST configuration
    API->>DB: Save immutable quote and reserve invoice number
    API-->>Client: checkout_id, invoice_no, total_paise, tax_paise, offers
    Note over Client,Shopify: No payment, order or stock reservation yet
    Reviewer->>Client: Confirm quoted amount
    Client->>API: POST /sales/{checkout_id}/complete
    API->>Terminal: Charge the saved amount for UPI/card
    Terminal-->>API: charge_id
    API->>DB: Save captured payment reference
    API->>Shopify: POST paid order with lines, taxes, discounts, location and references
    Shopify-->>API: Source order ID; tracked stock decremented
    API->>DB: Save order ID; mark order_recorded and invoice issued
    API-->>Client: Durable checkout state
    Client->>API: GET /api/checkouts/{identifier}/detail
    API->>Shopify: GET the source order
    API-->>Client: Saved quote + actual source order + refund attempts
```

For cash, there is no electronic terminal charge; an open drawer is required. A company-funded remake can have zero customer charge. Neither exception should be narrated as a terminal capture.

## Swagger-only walkthrough

### 1. Authenticate — frontend not required

Open `/docs`, expand **00 · Access → POST /auth/login**, choose **Try it out**, and enter a provisioned username/password from your private local account file. Use `manager` for HSR or `admin` for the complete walkthrough. Do not show the password while recording.

Swagger sends the login request and the browser keeps the session cookie. Its request interceptor obtains the session CSRF token and attaches it to subsequent mutations. GET `/auth/me` proves the role/store identity. No frontend page or manual cookie copying is necessary.

### 2. Show inputs arriving from external systems

- `GET /api/bootstrap`: inspect store `HSR`, staff `S108` and catalog variants. This reads Shopify locations/products and SMT staff; the customer directory is the local fixture aid.
- `POST /api/customers` with JSON body `{"phone":"9000000005"}`: inspect the normalized customer phone, tags and prescriptions. No phone is included in the request URL. The default runner uses body-based mock-wrapper lookups upstream too.
- `GET /api/inventory?store_code=HSR`: note the chosen frame's `inventory_item_id` and available quantity. For frame variant `91000003`, the inventory item is `92000003`.

Explain: “These are source records. I haven't created a bill or moved money.”

### 3. Prepare the bill

In `POST /sales/prepare`, select the **single_pair** example:

```json
{
  "phone": "+919000000005",
  "store_code": "HSR",
  "staff_id": "S108",
  "variant_ids": [91000003, 91000083],
  "payment_method": "upi",
  "channel": "walk_in"
}
```

`S108` matches the manager account. A cashier must use their own `S105` staff identity. If a frame is out of stock after repeated demos, choose an available Rx-compatible frame from the catalog and inventory. The **family** example shows three independently validated wearers on one invoice.

Expand **Schema** to show `WearerSelection`, then execute. Explain the response:

- `checkout_id`: the app's durable reference, used in subsequent requests.
- `invoice_no`: the app's per-store invoice sequence, not Shopify's global order number.
- `total_paise`: the exact amount awaiting confirmation.
- `tax_paise`: tax already included in the price, not added again.
- `offers`: applied/rejected decisions with reasons.
- `status: draft`: still no charge, no source order, no physical stock reservation.

### 4. Show the prepared source payload

Call `GET /api/checkouts/{identifier}/detail` with that checkout ID. Inspect:

- `quote.order_payload.customer.id`: the source customer link.
- `location_id`: the billing-store source location.
- `line_items`: source variants, prices, discounts, tax lines, HSN and wearer Rx properties.
- `note_attributes`: invoice number, checkout ID, staff, channel and payment method.
- `order: null`: proves no source order exists at this stage.

This is the persisted prepared order body. **Completion adds the payment `transactions` array before sending it**, so do not call the prepayment payload the exact final request byte-for-byte.

### 5. Confirm and inspect the result

Call `POST /sales/{checkout_id}/complete`. Explain: “For this UPI bill, the app charges the terminal first, records that reference, then creates a paid Shopify order.”

Expected status: `order_recorded`. Record `payment_charge_id` and `shopify_order_id`.

Call detail again and expand **`order`**. This is read back from the source mock, not reconstructed from the quote. Show source order/line IDs, successful payment transaction, line-level tax, metadata and financial status. Repeat the inventory read to show the frame count fell by one. The invoice remains linked through `note_attributes`.

Repeating an already successful completion returns the same order. An uncertain result is not permission to try charging again.

### 6. Refund and show the write-back

Call `POST /refunds/prepare` with the checkout ID and a reason. Internally this reads the source order and calls Shopify's refund calculation endpoint. The calculation uses POST, but does **not** move money or restock.

Copy `refund_id`, inspect the amount/tax, then call `POST /refunds/{refund_id}/complete`.

The app refunds the terminal, records that reference, then creates the Shopify refund. Read detail again:

- `order.refunds`: proves the refund exists in the source system.
- Source refund lines: frames have `return` at the original location; lenses have `no_restock`.
- Source refund transactions and original-line tax: prove the reversal.
- `refunds` at the detail root: local recovery records, distinct from `order.refunds`.

Repeat inventory to verify the original frame quantity is restored.

### 7. Read the final result into reporting

Call `GET /api/reports` with the actual sale day and `store_code=HSR`. It reads source orders/refunds and computes store/channel totals, refunds by event date, net collections and payment-to-order delta. Compare before/after refund rather than expecting all totals to be zero—other demo bills may exist.

The older `/reports/day-end` keeps its original order-date semantics: refunds are attached to the selected day's orders, even if made later. Explain which report you're showing.

## If the tech lead asks about outages

Use `GET /checkouts/{checkout_id}` to show saved state. Quote, payment and order states are separate because a terminal capture can succeed while order creation fails. Known uncertain source order/refund states can be reconciled by searching existing identifiers. Unknown terminal outcomes require investigation; the app does not promise safe automatic retries that the mock cannot guarantee.

The supplied mock is not a live Shopify integration. A real pilot requires actual provider contracts, scopes, location mapping, pagination/settlement and business sign-off. The demo proves workflow and state handling against the supplied contract.
