"""Sale orchestration, including distinct-variant multi-pair carts."""

from datetime import datetime
from collections import Counter
from uuid import uuid4
from app.domain.models import (
    Cart,
    CartLine,
    CheckoutStatus,
    Customer,
    LensConfiguration,
)
from app.domain.errors import StateConflict
from app.domain.errors import GatewayError
from app.constants import INDIA, PAYMENT_METHODS, SALES_CHANNELS
from app.gateways.contracts import SaleGateway
from app.persistence.contracts import SaleRepository
from app.services.prescriptions import validate_lens, latest_valid_prescription
from app.services.offers import evaluate_offers
from app.services.taxes import inclusive_tax_line, invoice_totals
from app.services.catalog import load_json, tax_catalog
from app.services.pairing import frame_lens_pairs
from app.phone import normalize_phone


class SaleValidationError(ValueError):
    pass


class SaleService:
    # Initialize the adapter or service with its explicit dependencies.
    def __init__(self, store: SaleRepository, gateway: SaleGateway):
        "Initialize the adapter or service with its explicit dependencies."
        self.store = store
        self.gateway = gateway

    # Read live mock records, validate and persist an immutable sale quote BEFORE charging.
    def prepare(
        self,
        *,
        phone,
        store_code,
        staff_id,
        variant_ids,
        payment_method="upi",
        channel="walk_in",
        on_date=None,
        manager_role=None,
        reason_code=None,
        override_bps=None,
        selected_offer_id=None,
        checkout_id=None,
        members=None,
        remake=None,
    ):
        """Read live mock records, validate and persist an immutable sale quote BEFORE charging."""
        phone = normalize_phone(phone)
        if members:
            members = [
                {**member, "phone": normalize_phone(member["phone"])}
                for member in members
            ]
        on_date = on_date or datetime.now(INDIA).date()
        member_phones = []
        pair_refs = {}
        if members:
            variant_ids = []
            for number, member in enumerate(members, 1):
                if not self.gateway.customer(member["phone"]):
                    raise SaleValidationError(
                        "Family member must be an existing customer"
                    )
                selected = member.get("variant_ids", [])
                lens_only = member.get("lens_only_variant_ids", [])
                frame_only = member.get("frame_only_variant_ids", [])
                if not 1 <= len(selected) + len(lens_only) + len(frame_only) <= 30:
                    raise SaleValidationError(
                        "Each wearer needs between 1 and 30 frame, paired-lens or lens-only units"
                    )
                selected_variants = [self.gateway.variant(item) for item in selected]
                offset = len(variant_ids)
                selected_kinds = [variant["metadata"]["line_type"] for variant in selected_variants]
                optical = [index for index, variant in enumerate(selected_variants)
                           if variant["metadata"]["line_type"] == "frame"
                           and variant["metadata"].get("category") != "sunglasses"]
                try:
                    pairs = frame_lens_pairs(selected_kinds, optical)
                except ValueError as error:
                    raise SaleValidationError(str(error)) from error
                for pair_number, (frame, lens) in enumerate(pairs, 1):
                    pair_refs[offset + frame] = pair_refs[offset + lens] = f"{number}:{pair_number}"
                for item in selected:
                    variant_ids.append(item)
                    member_phones.append(member["phone"])
                for item in lens_only:
                    standalone_lens = self.gateway.variant(item)
                    if standalone_lens["metadata"]["line_type"] != "lens":
                        raise SaleValidationError(
                            "Lens-only selections must use lens variants"
                        )
                    variant_ids.append(item)
                    member_phones.append(member["phone"])
                for item in frame_only:
                    if self.gateway.variant(item)["metadata"]["line_type"] != "frame":
                        raise SaleValidationError("Frame-only selections must use frame variants")
                    variant_ids.append(item)
                    member_phones.append(member["phone"])
        if payment_method not in PAYMENT_METHODS:
            raise SaleValidationError("Choose UPI, card or cash")
        if channel not in SALES_CHANNELS:
            raise SaleValidationError("Unknown sales channel")
        if not variant_ids or any(
            not isinstance(variant, int) for variant in variant_ids
        ):
            raise SaleValidationError("variant_ids must contain numeric variant IDs")
        locations = [
            l
            for l in self.gateway.locations()
            if l["store_code"] == store_code and l["kind"] == "store"
        ]
        if len(locations) != 1:
            raise SaleValidationError("Unknown billing store")
        location = locations[0]
        customer_raw = self.gateway.customer(phone)
        if not customer_raw:
            raise SaleValidationError("Existing customer not found in Shopify")
        staff = next(
            (s for s in self.gateway.staff(store_code) if s["staff_id"] == staff_id),
            None,
        )
        if not staff:
            raise SaleValidationError("Staff member not found in this store")
        if override_bps is not None:
            if not staff.get("can_override_discount") or not reason_code:
                raise SaleValidationError(
                    "Manager override needs authorized staff and reason"
                )
            if selected_offer_id not in (None, "MANAGER_OVERRIDE"):
                raise SaleValidationError(
                    "Choose either a manager discount or one coupon, not both"
                )
            selected_offer_id = "MANAGER_OVERRIDE"
            manager_role = "store_manager"
        elif selected_offer_id == "MANAGER_OVERRIDE":
            raise SaleValidationError("Enter a manager discount percentage")
        variants = [self.gateway.variant(variant) for variant in variant_ids]
        kinds = [variant["metadata"]["line_type"] for variant in variants]
        if any(
            kind not in ("frame", "lens", "sunglass", "sunglasses") for kind in kinds
        ):
            raise SaleValidationError("Unsupported product category")
        if not members and len(variant_ids) != len(set(variant_ids)):
            raise SaleValidationError(
                "Duplicate variant IDs are not supported; select distinct variants"
            )
        frame_positions = [
            line_index for line_index, kind in enumerate(kinds) if kind == "frame"
        ]
        lens_positions = [
            line_index for line_index, kind in enumerate(kinds) if kind == "lens"
        ]
        if not members:
            optical = [index for index in frame_positions if variants[index]["metadata"].get("category") != "sunglasses"]
            try:
                pairs = frame_lens_pairs(kinds, optical, allow_lens_only=True)
            except ValueError as error:
                raise SaleValidationError(str(error)) from error
            for number, (frame, lens) in enumerate(pairs, 1):
                pair_refs[frame] = pair_refs[lens] = str(number)
        for line_index in frame_positions:
            if (
                line_index in pair_refs
            ) and not variants[line_index]["metadata"].get("rx_able"):
                raise SaleValidationError(
                    "Selected frame is not prescription-compatible"
                )
        quantities = Counter(
            variant["inventory_item_id"]
            for variant in variants
            if variant.get("inventory_item_id")
        )
        for line_index in [
            index
            for index, variant in enumerate(variants)
            if variant.get("inventory_item_id")
        ]:
            if (
                self.gateway.stock(
                    variants[line_index]["inventory_item_id"], location["id"]
                )
                < quantities[variants[line_index]["inventory_item_id"]]
            ):
                raise SaleValidationError(
                    f"Frame out of stock at selected store: {variants[line_index]['sku']}"
                )
        rx = None
        prescriptions_by_line = {}
        if lens_positions:
            for line_index in lens_positions:
                wearer_phone = member_phones[line_index] if members else phone
                rx_rows = self.gateway.prescriptions(wearer_phone)
                rx = latest_valid_prescription(rx_rows, on_date=on_date)
                if not rx:
                    raise SaleValidationError(
                        "No valid prescription available for " + wearer_phone
                    )
                prescriptions_by_line[line_index] = rx
                lens = variants[line_index]
                meta = lens["metadata"]
                validation = validate_lens(
                    rx,
                    LensConfiguration(
                        meta["lens_type"],
                        str(meta["index"]),
                        meta["coating"],
                        str(lens["id"]),
                    ),
                    meta,
                    on_date=on_date,
                )
                if not validation.valid:
                    raise SaleValidationError(
                        f"Lens {lens['sku']}: " + "; ".join(validation.reasons)
                    )
        customer = Customer(
            str(customer_raw["id"]),
            phone,
            tuple(
                x.strip() for x in customer_raw.get("tags", "").split(",") if x.strip()
            ),
        )
        lines = tuple(
            CartLine(
                variant["sku"],
                str(variant["id"]),
                1,
                variant["price_paise"],
                variant["metadata"]["line_type"],
                pair_refs.get(line_index),
                prescriptions_by_line[line_index].prescription_id
                if line_index in prescriptions_by_line
                else None,
            )
            for line_index, variant in enumerate(variants)
        )
        cart = Cart(customer.customer_id, store_code, lines)
        discounts = evaluate_offers(
            cart,
            customer,
            load_json("offers.json"),
            on_date=on_date,
            lens_metadata={
                str(variant["id"]): variant["metadata"] for variant in variants
            },
            manager_role=manager_role,
            reason_code=reason_code,
            override_bps=override_bps,
            selected_offer_id=selected_offer_id,
        )
        if selected_offer_id is not None:
            selected_decision = next(
                decision
                for decision in discounts.decisions
                if decision.offer_id == selected_offer_id
            )
            if not selected_decision.applied:
                raise SaleValidationError(
                    f"Coupon {selected_offer_id} cannot be applied: {selected_decision.reason}"
                )
        line_discounts = discounts.discounts_paise
        if remake and remake["cost_owner"] != "customer":
            line_discounts = tuple(line.unit_price_paise for line in lines)
        catalog = tax_catalog()
        taxes = tuple(
            inclusive_tax_line(
                hsn=variant["metadata"]["hsn"],
                quantity=1,
                unit_price_paise=lines[line_index].unit_price_paise,
                discount_paise=line_discounts[line_index],
                rate_bps=catalog.rate_for(variant["metadata"]["hsn"], on_date),
            )
            for line_index, variant in enumerate(variants)
        )
        totals = invoice_totals(taxes)
        if totals["total_paise"] <= 0 and not remake:
            raise SaleValidationError("Zero-charge transactions are outside Stage 5")
        checkout_identifier = checkout_id or str(uuid4())
        self.store.create_checkout(
            store_code, customer.customer_id, checkout_identifier
        )
        invoice = self.store.reserve_invoice(
            checkout_identifier, store_code, location["invoice_prefix"]
        )
        payload = self.gateway.build_order_payload(
            variants=variants,
            taxes=taxes,
            pair_refs=pair_refs,
            lens_positions=lens_positions,
            prescriptions_by_line=prescriptions_by_line,
            member_phones=member_phones,
            members=members,
            phone=phone,
            discounts=discounts,
            invoice=invoice,
            checkout_identifier=checkout_identifier,
            store_code=store_code,
            channel=channel,
            staff_id=staff_id,
            payment_method=payment_method,
            reason_code=reason_code,
            override_bps=override_bps,
            remake=remake,
            line_discounts=line_discounts,
            location=location,
            customer_raw=customer_raw,
        )
        quote = {
            "checkout_id": checkout_identifier,
            "invoice_no": invoice,
            "total_paise": totals["total_paise"],
            "tax_paise": totals["cgst_paise"] + totals["sgst_paise"],
            "method": payment_method,
            "order_payload": payload,
            "offer_decisions": [decision.__dict__ for decision in discounts.decisions],
            "remake": remake,
            "customer": customer_raw,
            "lines": [
                {
                    "title": variant["sku"] + " / " + variant["title"],
                    "variant_id": variant["id"],
                    "wearer_phone": member_phones[line_index] if members else phone,
                    "rx_id": prescriptions_by_line[line_index].prescription_id
                    if line_index in prescriptions_by_line
                    else None,
                    **taxes[line_index].__dict__,
                }
                for line_index, variant in enumerate(variants)
            ],
        }
        self.store.save_quote(checkout_identifier, quote)
        return {
            "checkout_id": checkout_identifier,
            "invoice_no": invoice,
            "total_paise": totals["total_paise"],
            "tax_paise": quote["tax_paise"],
            "offers": quote["offer_decisions"],
            "status": "draft",
        }

    # Perform one external charge and one order POST, never blindly retry unsafe writes.
    def complete(self, checkout_id):
        """Perform one external charge and one order POST, never blindly retry unsafe writes."""
        state = self.store.get_checkout(checkout_id)
        if state["status"] == CheckoutStatus.ORDER_RECORDED.value:
            self.store.mark_invoice_issued(checkout_id)
            return state
        if state["status"] != CheckoutStatus.DRAFT.value:
            raise StateConflict(
                "Checkout already started: inspect/reconcile; do not charge again"
            )
        quote = self.store.load_quote(checkout_id)
        if not quote:
            raise StateConflict("Missing persisted quote")
        # Quotes do not reserve stock. Reject a stale cart before any payment side effect.
        demand = Counter()
        location_id, selected_units = self.gateway.quote_inventory(quote)
        for variant_id, quantity in selected_units:
            variant = self.gateway.variant(variant_id)
            if variant.get("inventory_item_id"):
                demand[variant["inventory_item_id"]] += quantity
        for item, quantity in demand.items():
            if self.gateway.stock(item, location_id) < quantity:
                raise StateConflict(
                    "Stock changed since quote; review the bill before payment"
                )
        payment_reference = "elu-checkout-" + checkout_id
        self.store.record_external_ref(checkout_id, "payment_ref", payment_reference)
        self.store.change_status(
            checkout_id, CheckoutStatus.DRAFT, CheckoutStatus.PAYMENT_PENDING
        )
        try:
            charged = (
                {"charge_id": "cash-" + checkout_id}
                if quote["method"] == "cash"
                else {"charge_id": "no-charge-" + checkout_id}
                if quote["total_paise"] == 0
                else self.gateway.charge(
                    payment_reference, quote["total_paise"], quote["method"]
                )
            )
        except GatewayError as exc:
            self.store.change_status(
                checkout_id,
                CheckoutStatus.PAYMENT_PENDING,
                CheckoutStatus.PAYMENT_UNCERTAIN,
                error_detail=str(exc),
            )
            raise
        self.store.record_external_ref(
            checkout_id, "payment_charge_id", charged["charge_id"]
        )
        self.store.change_status(
            checkout_id, CheckoutStatus.PAYMENT_PENDING, CheckoutStatus.PAYMENT_CAPTURED
        )
        return self._record_order(checkout_id, quote, charged["charge_id"])

    # Record the paid order once and advance the invoice register to issued.
    def _record_order(self, checkout_id, quote, charge_id):
        self.store.change_status(
            checkout_id, CheckoutStatus.PAYMENT_CAPTURED, CheckoutStatus.ORDER_PENDING
        )
        payload = self.gateway.paid_payload(quote, charge_id)
        self.store.save_order_submission(checkout_id, payload)
        try:
            order = self.gateway.order(payload)
        except GatewayError as exc:
            self.store.change_status(
                checkout_id,
                CheckoutStatus.ORDER_PENDING,
                CheckoutStatus.ORDER_UNCERTAIN,
                error_detail=str(exc),
            )
            raise
        self.store.record_external_ref(
            checkout_id, "shopify_order_id", str(order["id"])
        )
        self.store.change_status(
            checkout_id, CheckoutStatus.ORDER_PENDING, CheckoutStatus.ORDER_RECORDED
        )
        self.store.mark_invoice_issued(checkout_id)
        return self.store.get_checkout(checkout_id)

    # Read-only reconciliation; Shopify may lack the order. Never re-post automatically.
    def reconcile_order(self, checkout_id):
        """Read-only reconciliation; Shopify may lack the order. Never re-post automatically."""
        state = self.store.get_checkout(checkout_id)
        if state["status"] != CheckoutStatus.ORDER_UNCERTAIN.value:
            raise StateConflict("Reconciliation only permitted for order_uncertain")
        matches = [
            o for o in self.gateway.orders() if o["checkout_reference"] == checkout_id
        ]
        if len(matches) == 1:
            self.store.record_external_ref(
                checkout_id, "shopify_order_id", str(matches[0]["id"])
            )
            self.store.change_status(
                checkout_id,
                CheckoutStatus.ORDER_UNCERTAIN,
                CheckoutStatus.ORDER_RECORDED,
            )
            self.store.mark_invoice_issued(checkout_id)
        elif len(matches) > 1:
            self.store.change_status(
                checkout_id,
                CheckoutStatus.ORDER_UNCERTAIN,
                CheckoutStatus.RECONCILIATION_REQUIRED,
                error_detail="Duplicate matching orders: manual intervention",
            )
        return self.store.get_checkout(checkout_id)
