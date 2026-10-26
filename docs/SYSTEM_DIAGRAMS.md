# Submission diagrams — current implementation

These diagrams describe the implemented demo. Runtime integration dictionaries still couple some application orchestration to Shopify; pure domain rules are provider-independent. Not all database relationships are enforced foreign keys.

## Class relationships

```mermaid
classDiagram
Customer "1" --> "0..*" Cart : payer
Cart "1" *-- "1..*" CartLine : lines
CartLine --> Prescription : optional Rx ID
Prescription *-- EyePower : right and left
CartLine --> LensConfiguration : lens variant
SaleService ..> Cart : builds
SaleService ..> TaxLine : calculates
SaleService ..> OfferResult : evaluates
SaleService --> SaleGateway : injected
RefundService --> RefundGateway : injected
DayEndService --> ReportingGateway : injected
SaleService --> SQLiteStore : saves intent
RefundService --> SQLiteStore : saves reversal
MockHTTP ..|> SaleGateway : structural protocol
MockHTTP ..|> RefundGateway : structural protocol
MockHTTP ..|> ReportingGateway : structural protocol
OperationsGateway --|> MockHTTP : clinical overlay
MockHTTP --> ShopifyMapping : serialization
class SaleService {
  prepare()
  complete(checkout_id)
  reconcile_order(checkout_id)
}
class RefundService {
  prepare()
  complete(refund_id)
  reconcile_shopify(refund_id)
}
class SQLiteStore {
  save_quote()
  change_status()
  reserve_invoice()
}
```

## Payment/order sequence

```mermaid
sequenceDiagram
actor Cashier
participant API
participant SaleService
participant DB as SQLiteStore
participant Terminal
participant Shopify
Cashier->>API: POST /sales/prepare
API->>SaleService: authenticated preparation
SaleService->>Shopify: read customer, variant, store, stock
Note over SaleService: Rx from store tool; validate offers and tax
SaleService->>DB: persist quote and invoice allocation
API-->>Cashier: checkout_id and totals
Cashier->>API: POST /sales/{id}/complete
SaleService->>Shopify: recheck inventory
SaleService->>DB: claim payment_pending
SaleService->>Terminal: one charge
alt definite result
Terminal-->>SaleService: charge_id
SaleService->>DB: persist captured state
SaleService->>Shopify: create paid order
Shopify-->>SaleService: order_id
SaleService->>DB: record source ID and completion
API-->>Cashier: invoice
else timeout
SaleService->>DB: uncertain state
API-->>Cashier: inspect/reconcile, do not recharge
end
```

## Recovery states

```mermaid
stateDiagram-v2
[*] --> draft
draft --> payment_pending
payment_pending --> payment_captured
payment_pending --> payment_uncertain
payment_captured --> order_pending
order_pending --> order_recorded
order_pending --> order_uncertain
order_uncertain --> order_recorded: one source match
order_uncertain --> reconciliation_required: duplicate matches
```

## M1: Customer and latest valid prescription

```mermaid
flowchart LR
  n0["Cashier enters phone"]
  n1["POST /api/customers"]
  n2["Canonical +91 phone"]
  n3["Shopify customer + SMT Rx"]
  n4["Merge local clinical Rx"]
  n5["Select latest valid Rx"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```

## M2: Frame + lens selection and clinical validation

```mermaid
flowchart LR
  n0["Choose frame + lens"]
  n1["Resolve source variants"]
  n2["Attach wearer / pair"]
  n3["Load lens limits"]
  n4["Validate sphere/cylinder/ADD"]
  n5["Accept or block with reason"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```

## M3: Offers, dates, conditions and stackability

```mermaid
flowchart LR
  n0["Read offers.json"]
  n1["Check active/date/tag/pair"]
  n2["Evaluate eligible rules"]
  n3["Compare allowed combinations"]
  n4["Allocate exact line discounts"]
  n5["Persist decision + reason"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```

## M4: Inclusive GST and exact line arithmetic

```mermaid
flowchart LR
  n0["Gross MRP in paise"]
  n1["Subtract line discount"]
  n2["HSN + effective date"]
  n3["Extract taxable amount"]
  n4["Split tax deterministically"]
  n5["Sum invoice invariants"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```

## M5: Payment, source order and store invoice

```mermaid
flowchart LR
  n0["Persist quote + invoice"]
  n1["Recheck stock"]
  n2["Claim payment_pending"]
  n3["Charge terminal / cash"]
  n4["POST source order"]
  n5["Save order ID + receipt"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```

## M6: Full refund, original tax and correct stock

```mermaid
flowchart LR
  n0["Read original source sale"]
  n1["Calculate full reversal"]
  n2["Verify amount + original tax"]
  n3["Persist refund attempt"]
  n4["Refund terminal / cash"]
  n5["Record source refund"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```

## M7: Store/date day-end and central totals

```mermaid
flowchart LR
  n0["Choose store + India date"]
  n1["Read source orders"]
  n2["Filter valid store sales"]
  n3["Sum gross/discount/tax"]
  n4["Sum refunds + methods"]
  n5["Return reconciled report"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```

## S1: Cash till, paid-ins, paid-outs and close

```mermaid
flowchart LR
  n0["Open with float"]
  n1["Record cash sales/refunds"]
  n2["Add reasoned paid-in"]
  n3["Record reasoned paid-out"]
  n4["Count physical cash"]
  n5["Close + variance alert"]
  n0 --> n1
  n1 --> n2
  n2 --> n3
  n3 --> n4
  n4 --> n5
```
