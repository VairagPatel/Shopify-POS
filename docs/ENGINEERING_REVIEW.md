> Update: the final submission pass added BillingAdapter neutral records and repository ports, with a replacement-provider sale/refund/report test. See docs/FINAL_REQUIREMENT_AUDIT.md. The assessment below records the earlier intermediate refactor.

# Engineering review — 26 October 2026

This review covers phone privacy, schema traceability, SOLID, shared policies, naming, adapters and lifecycle practices. It is not a claim that the application is fully production-ready or a completely isolated hexagonal architecture.

## Phone lookup and storage

Current frontend request:

```http
POST /api/customers
Content-Type: application/json

{"phone":"9000000000"}
```

The normalized value is `+919000000000`. The same normalization applies to supported `+91`, bare digits, `91`-prefixed and domestic-zero forms at lookup, sale/member, clinical, remake and draft boundaries. Existence is a separate check: a valid phone can still return 404 when no customer exists.

`GET /api/customers?phone=...` is not a supported route in the current source. The old GET returns 405 when authenticated. The app cannot stop an arbitrary old client from sending a URL it constructs; it can stop accepting that contract and keep its own clients/logs clean. Standard frontend lookup sends JSON and standard upstream lookups use private wrapper POST extensions. Original exercise GET mode remains explicit compatibility mode and is not privacy-equivalent.

No app was listening at port 8001 during the local verification attempt. The specific old URL therefore could not be tied to an active process. Restart the runner from this workspace and refresh the page before judging the current contract. Do not delete the database to update the app.

Historical source/quote records are not silently rewritten. A mixed-format data migration needs backup, duplicate detection and an approved identity merge policy. Phones are not inherently unique person identifiers for a family. Normalization is not OTP verification, encryption or full PII removal.

## Schema and API traceability

| Stage | Internal contract / implementation | External call or storage |
| --- | --- | --- |
| Lookup request | CustomerLookupRequest → PhoneNumber → normalize_phone | POST /eluno/customer-lookup in standard demo wrapper |
| Clinical context | CustomerLookupResponse → CustomerRecord + PrescriptionRecord list | POST /eluno/prescription-lookup plus local prescriptions |
| New clinical entry | PrescriptionInput / EyeInput; role guard | Local Rx with source customer ID and canonical phone |
| Cart preparation | PrepareRequest / WearerSelection → SaleService | Source variants, locations, stock, staff and prescriptions |
| Pricing | Offer evaluation + TaxLine + invoice totals | Configured offers/rates, then persisted quote |
| Payment/order | Saved checkout and immutable quote | Terminal charge then source order with transaction |
| Refund | RefundPrepareRequest → RefundService | Source refund calculation, terminal reversal, source refund |
| Reporting | DayEndService / analytics | Source orders and refunds, local drawer data |

See `app/static/api-schema-guide.html` for full example bodies, 32 internal operations, 20 reusable schemas, external contracts and 15 table definitions. `docs/openapi-contract.json` is generated from application OpenAPI. Regenerate with `python scripts/build_schema_guide.py` after contract changes. A generic dictionary schema remains generic; documentation does not create runtime validation that is absent in code.

Financial traceability uses checkout ID, invoice number, payment reference, source order ID and refund ID. This is not full distributed tracing. A future correlation/logging implementation must avoid collecting phone/clinical payloads unnecessarily.

## Implemented architecture improvements

- `app/constants.py` centralizes shared business/runtime policies: timezone, mock address/version, retry limits, order cap, money units, discount/variance thresholds, authentication limits and phone format definitions. Ordinary tax rates and offers remain data files. Local mathematical constants and HTTP status values do not all need meaningless global names.
- `app/domain/money.py` owns currency conversion. Refund/reporting no longer import sale orchestration just to convert money. Sale retains compatible imports for existing callers.
- `app/domain/errors.py` owns shared provider/state failures. Existing adapter/persistence imports re-export the same classes so catch behavior remains compatible.
- `app/gateways/contracts.py` now describes actual adapter methods. Previously the protocols declared unused method names that did not match the working adapter.
- Sale, refund and reporting receive gateway protocols through constructors and no longer import concrete HTTP/SQLite exception modules.
- Pricing/mapping loop identifiers now use names such as `variant`, `decision`, `line_index`, `application_index`, `properties` and `eye_record`. Public JSON keys and stored fields are preserved.

## SOLID assessment

| Principle | Evidence | Remaining limitation |
| --- | --- | --- |
| Single responsibility | Separate clinical, offer, tax, money, error and transport modules | Web orchestration and sale mapping are still large |
| Open/closed | Ordinary pricing changes are configuration; gateways are injected | New rule types/provider shapes still require code work |
| Liskov substitution | Adapter exposes active ports; tests check presence and existing workflows | Runtime Protocol checks are not semantic/type proof; alternate adapters need contract suites |
| Interface segregation | Separate sale/refund/reporting capability protocols | Some broad combined adapter capabilities remain |
| Dependency inversion | Services import ports and domain errors instead of HTTP error implementations | Provider dictionaries and direct persistence access remain |

An adapter pattern exists and is used. Full ports-and-adapters isolation is **partial**. Proposed next refactor: typed provider-neutral DTOs, serialization in adapters, repository ports, and composition-root wiring with independent provider contract tests. Do not tell a reviewer that changing Shopify requires only replacing the HTTP client today.

## Software lifecycle and change control

Requirements: stakeholder reply, unresolved policy owners and the problem-led HLD. Design: component/data ownership, state transitions, schema guide and LLD. Implementation: focused reversible changes preserving external data. Verification: domain tests, integration fixtures, role matrix, browser tests and architecture guards. Release: review diff, regenerate artifacts, run setup/start instructions and obtain actual business/provider acceptance. Operation: reconcile exceptions, monitor delivery and prove backups/restores.

Existing documents support these practices, but they do not prove formal stakeholder sign-off, a CI deployment pipeline, live monitoring, production penetration testing or seven-store rollout. The HLD's work packages are proposed planning divisions, not a fabricated historical ticket record.

## Verification result

Full regression suite: **337 passed**, one third-party Starlette/httpx deprecation warning, in 170.10 seconds. Command: `.venv\Scripts\python.exe -m pytest tests -q --tb=short`. This includes current phone normalization/privacy and browser checks plus four new architecture-contract guards. Output is in ignored `runtime/architecture-suite.txt`.

The supplied exercise mock was not edited. No live Shopify/payment calls or historical-data rewrite was performed. Changes remain local pending review/push.

## Start the current version

Stop an old runner with Ctrl+C in its terminal, then run from the project directory:

```powershell
.\.venv\Scripts\python.exe run_demo.py --port 8001 --mock-port 8788
```

Refresh the browser. In Network, customer lookup must show POST `/api/customers`, with phone under Request Payload, not Query String Parameters. Swagger must show the request-body model. New clinical/draft/quote records use the canonical phone. Do not enable `ELUNO_PRIVATE_LOOKUP=0` when demonstrating the no-phone-in-URL requirement.
