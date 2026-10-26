"""Shopify-specific order serialization, separate from clinical/pricing rules."""

import json
from app.domain.money import money
from app.constants import BASIS_POINTS_PER_UNIT


# Translate an approved pricing result into the exercise provider's order shape.
def build_order_payload(
    *,
    variants,
    taxes,
    pair_refs,
    lens_positions,
    prescriptions_by_line,
    member_phones,
    members,
    phone,
    discounts,
    invoice,
    checkout_identifier,
    store_code,
    channel,
    staff_id,
    payment_method,
    reason_code,
    override_bps,
    remake,
    line_discounts,
    location,
    customer_raw,
):
    payload_lines = []
    for line_index, variant in enumerate(variants):
        tax = taxes[line_index]
        properties = [
            {"name": "line_type", "value": variant["eluno"]["line_type"]},
            {"name": "hsn", "value": tax.hsn},
        ]
        if line_index in pair_refs:
            properties.append({"name": "pair_ref", "value": pair_refs[line_index]})
        if line_index in lens_positions:
            properties.extend(
                [
                    {
                        "name": "rx_id",
                        "value": prescriptions_by_line[line_index].prescription_id,
                    },
                    {
                        "name": "rx_snapshot",
                        "value": json.dumps({
                            "rx_id": prescriptions_by_line[line_index].prescription_id,
                            "valid_until": prescriptions_by_line[line_index].valid_until.isoformat(),
                            "od": {
                                "sph": prescriptions_by_line[line_index].right.sphere,
                                "cyl": prescriptions_by_line[line_index].right.cylinder,
                                "axis": prescriptions_by_line[line_index].right.axis,
                                "add": prescriptions_by_line[line_index].right.add,
                            },
                            "os": {
                                "sph": prescriptions_by_line[line_index].left.sphere,
                                "cyl": prescriptions_by_line[line_index].left.cylinder,
                                "axis": prescriptions_by_line[line_index].left.axis,
                                "add": prescriptions_by_line[line_index].left.add,
                            },
                        }, separators=(",", ":")),
                    },
                    {
                        "name": "wearer_phone",
                        "value": member_phones[line_index] if members else phone,
                    },
                    {
                        "name": "lens_config",
                        "value": f"{variant['eluno']['lens_type']}/{variant['eluno']['index']}/{variant['eluno']['coating']}",
                    },
                ]
            )
        payload_lines.append(
            {
                "variant_id": int(variant["id"]),
                "quantity": 1,
                "price": money(tax.gross_paise),
                "total_discount": money(tax.discount_paise),
                "properties": properties,
                "tax_lines": [
                    {
                        "title": key,
                        "rate": tax.rate_bps / (2 * BASIS_POINTS_PER_UNIT),
                        "price": money(getattr(tax, key.lower() + "_paise")),
                    }
                    for key in ("CGST", "SGST")
                ],
            }
        )
    applications = []
    for decision in discounts.decisions:
        if decision.applied:
            applications.append(
                {
                    "type": "manual",
                    "title": decision.offer_id,
                    "value": money(decision.amount_paise),
                    "value_type": "fixed_amount",
                    "allocation_method": "each",
                    "target_selection": "explicit",
                    "target_type": "line_item",
                }
            )
    for line_index, line in enumerate(payload_lines):
        allocations = []
        for application_index, decision in enumerate(
            [decision for decision in discounts.decisions if decision.applied]
        ):
            if decision.allocations_paise[line_index]:
                allocations.append(
                    {
                        "amount": money(decision.allocations_paise[line_index]),
                        "discount_application_index": application_index,
                    }
                )
        line["discount_allocations"] = allocations
    notes = [
        {"name": k, "value": str(variant)}
        for k, variant in {
            "invoice_no": invoice,
            "checkout_id": checkout_identifier,
            "store_code": store_code,
            "channel": channel,
            "staff_id": staff_id,
            "payment_method": payment_method,
            "discount_reason": reason_code or "",
            "discount_approver": staff_id if override_bps is not None else "",
            "remake": json.dumps(remake) if remake else "",
        }.items()
    ]
    if remake and remake["cost_owner"] != "customer":
        applications = [
            {
                "type": "manual",
                "title": "REMAKE_COST_ALLOCATION",
                "value": money(sum(line_discounts)),
                "value_type": "fixed_amount",
                "allocation_method": "each",
                "target_selection": "explicit",
                "target_type": "line_item",
            }
        ]
        for index, line in enumerate(payload_lines):
            line["discount_allocations"] = [
                {
                    "amount": money(line_discounts[index]),
                    "discount_application_index": 0,
                }
            ]
    payload = {
        "taxes_included": True,
        "location_id": location["id"],
        "inventory_behaviour": "decrement_obeying_policy",
        "source_name": "eluno-pos",
        "customer": {"id": customer_raw["id"]},
        "note_attributes": notes,
        "line_items": payload_lines,
        "discount_applications": applications,
    }
    return payload
