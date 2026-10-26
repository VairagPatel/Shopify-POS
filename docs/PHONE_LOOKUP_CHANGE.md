# Customer lookup, schemas and phone privacy

## Implemented contract

`POST /api/customers` accepts `{"phone":"9000000005"}` in its JSON body and returns the source customer plus source/local prescriptions. It is a lookup, not registration. Requires a session and CSRF token. No source match returns 404. The old GET method now returns 405; clients must migrate.

Canonical Indian mobile string: `+919000000005`. Supported input examples: `9000000005`, `919000000005`, `09000000005`, `+91 90000-00005`. Malformed/foreign/numeric JSON input is rejected rather than guessed. Applied to lookup, clinical input, member/payer phones, remakes and saved wearer drafts. Historical source invoices/quotes are not rewritten. Mixed-format historical imports need a separate reviewed migration.

`app/customer_schemas.py` provides explicit `CustomerLookupRequest`, `CustomerLookupResponse`, `CustomerRecord`, `PrescriptionRecord`, `SourceEyeRecord`, `PrescriptionInput` and `EyeInput` contracts. Newly entered clinical records retain source `customer_id`, canonical phone, generated Rx ID, issue time and the authenticated clinician identity. Lookup returns the full prescription list; sale preparation chooses the latest unexpired prescription and attaches its Rx ID to the lens line.

## External boundary

The default `OperationsGateway` and `run_demo.py` use private lookup mode. The durable wrapper adds:

- `POST /eluno/customer-lookup` → `{customers: [...]}`
- `POST /eluno/prescription-lookup` → `{prescriptions: [...]}`

Both receive the phone in JSON, query existing synthetic source records directly and do not construct a phone URL. These are **our demo extensions**, not official Shopify APIs. No automatic fallback is used. Other source sale/refund calls remain on the original exercise routes. The supplied mock source file is unchanged.

Direct `MockHTTP` and explicit `ELUNO_PRIVATE_LOOKUP=0` support original exercise compatibility (used by existing raw-mock tests). That mode still uses upstream query-string phone lookup and is not privacy-equivalent. A live provider needs a separately approved body-based integration contract.

Uvicorn access records strip query strings; the durable wrapper logs only paths. This does not configure proxy/APM/body/error logging elsewhere, encrypt stored data or remove phone from authorized responses, clinical/quote payloads, source lens properties, receipts and browser drafts. HTTPS and data-minimization/retention controls remain production work. The synthetic bootstrap directory remains visible to authenticated users.

## New customer creation

Not implemented, per the user's chosen scope. The guide documents proposed registration and duplicate handling separately. No source customer-create route exists in the supplied original mock. Do not confuse “Add wearer” with creating a source customer. Long-term customer-ID-based clinical linking, shared family phone policy, phone changes and ownership verification also need design/sign-off.

## Verification

New regression tests cover canonical/invalid formats, URL-free default wrapper requests, wrapper/access-log redaction, prescription lookup across formats, canonical draft/quote persistence and the retired GET method. Browser checks use a bare ten-digit lookup and assert the generated request URLs contain no phone query or example phone value.

Final full suite: **333 passed** in 178 seconds. The strengthened browser journey using the private wrapper also passed separately. Both runs reported one dependency deprecation warning. HTML checks passed for navigation, search, mobile width, print expansion and JavaScript errors; desktop and mobile screenshots were generated for visual review.

The initial run caught a new test fixture that omitted ADD while selecting a progressive lens. The clinical guard correctly rejected it; the fixture was corrected without weakening validation.

## Running the change

Stop the old runner with Ctrl+C in its VS Code terminal and restart:

```powershell
.\.venv\Scripts\python.exe run_demo.py --port 8001 --mock-port 8788
```

Refresh the browser. This reloads the backend contract and private wrapper routes while retaining app/source data. Do not recreate `.venv` or reset the databases.

Read `/static/api-schema-guide.html` for field mappings, actual internal OpenAPI contracts, external API inventory, local table definitions and proposed registration. Regenerate the guide/spec after schema changes with `python scripts/build_schema_guide.py`.
