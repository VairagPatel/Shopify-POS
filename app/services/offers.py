"""Deterministic seeded offer rules; no network access or arbitrary code execution."""

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Sequence
from app.domain.models import Cart, Customer
from app.services.taxes import rounded_div


@dataclass(frozen=True)
class OfferDecision:
    offer_id: str
    applied: bool
    amount_paise: int
    reason: str
    allocations_paise: tuple[int, ...]


@dataclass(frozen=True)
class OfferResult:
    decisions: tuple[OfferDecision, ...]
    discounts_paise: tuple[int, ...]

    # Sum applied discounts in integer paise.
    @property
    def total_discount_paise(self) -> int:
        "Sum applied discounts in integer paise."
        return sum(self.discounts_paise)


# Proportional exact-paisa split with stable residual assignment.
def _allocate(
    amount: int, indices: Sequence[int], remaining: Sequence[int]
) -> tuple[int, ...]:
    """Proportional exact-paisa split with stable residual assignment."""
    result = [0] * len(remaining)
    total = sum(remaining[i] for i in indices)
    amount = min(amount, total)
    if total <= 0 or amount <= 0:
        return tuple(result)
    for i in indices:
        result[i] = amount * remaining[i] // total
    rest = amount - sum(result)
    # Stable largest-remainder tie-break by index
    rank = sorted(indices, key=lambda i: (-(amount * remaining[i] % total), i))
    for i in rank[:rest]:
        result[i] += 1
    return tuple(result)


# Apply highest-priority valid non-stackable OR valid stackable set, whichever saves more.
def evaluate_offers(
    cart: Cart,
    customer: Customer,
    offers: Sequence[Mapping],
    *,
    on_date: date,
    lens_metadata: Mapping[str, Mapping] | None = None,
    manager_role: str | None = None,
    reason_code: str | None = None,
    override_bps: int | None = None,
) -> OfferResult:
    """Apply highest-priority valid non-stackable OR valid stackable set, whichever saves more.

    This policy is a documented v1 interpretation, not confirmed business policy.
    """
    lens_metadata = lens_metadata or {}
    lines = cart.lines
    gross = [x.quantity * x.unit_price_paise for x in lines]
    pairs = {x.pair_ref for x in lines if x.pair_ref}
    pair_count = len(pairs) + sum(
        1 for x in lines if x.product_kind == "lens" and not x.pair_ref
    )
    candidates = []
    preliminary = {}
    for row in sorted(offers, key=lambda r: (int(r["priority"]), str(r["offer_id"]))):
        oid = str(row["offer_id"])
        rule = row["rule"]
        reason = None
        eligible = []
        if not row.get("active", False) or not date.fromisoformat(
            row["valid_from"]
        ) <= on_date <= date.fromisoformat(row["valid_to"]):
            reason = "inactive or outside offer date window"
        else:
            target = rule.get("applies_to")
            if target == "cart":
                eligible = list(range(len(lines)))
            elif target == "pair":
                refs = {
                    p
                    for p in pairs
                    if any(x.pair_ref == p and x.product_kind == "frame" for x in lines)
                    and any(x.pair_ref == p and x.product_kind == "lens" for x in lines)
                }
                eligible = [
                    i
                    for i, x in enumerate(lines)
                    if x.pair_ref in refs and x.product_kind in ("frame", "lens")
                ]
            elif target in ("frame", "lens"):
                eligible = [i for i, x in enumerate(lines) if x.product_kind == target]
            else:
                reason = f"unsupported applies_to {target}"
            cond = rule.get("condition", {})
            if cond.get("customer_tag") and cond["customer_tag"] not in customer.tags:
                reason = "customer tag required"
            if cond.get("min_pairs_in_cart") and pair_count < cond["min_pairs_in_cart"]:
                reason = "minimum pair count not met"
            if cond.get("has_frame_and_lens") and not eligible:
                reason = "complete frame-and-lens pair required"
            if any(k in cond for k in ("lens_type", "index_min", "coating")):
                # Check configured lens conditions before admitting an offer candidate.
                def lens_match(i):
                    "Check configured lens conditions before admitting an offer candidate."
                    meta = lens_metadata.get(lines[i].variant_id, {})
                    return (
                        (
                            not cond.get("lens_type")
                            or meta.get("lens_type") == cond["lens_type"]
                        )
                        and (
                            not cond.get("coating")
                            or meta.get("coating") == cond["coating"]
                        )
                        and (
                            not cond.get("index_min")
                            or float(meta.get("index", 0)) >= float(cond["index_min"])
                        )
                    )

                eligible = [i for i in eligible if lens_match(i)]
            requires = rule.get("requires", {})
            if requires.get("role") and manager_role != requires["role"]:
                reason = "manager authorization required"
            if requires.get("reason_code") and not reason_code:
                reason = "manager reason code required"
            if not eligible and not reason:
                reason = "no eligible cart lines"
        allocations = [0] * len(lines)
        if not reason:
            disc = rule["discount"]
            if disc["type"] == "percent" and "value_bps" in disc:
                bps = int(disc["value_bps"])
                if disc.get("on") == "lowest_priced_lens_line":
                    eligible = [min(eligible, key=lambda i: (gross[i], i))]
                for i in eligible:
                    allocations[i] = rounded_div(gross[i] * bps, 10000)
            elif disc["type"] == "flat":
                allocations = list(_allocate(int(disc["value_paise"]), eligible, gross))
            elif "value_bps_max" in disc:
                if override_bps is None or not 0 <= override_bps <= int(
                    disc["value_bps_max"]
                ):
                    reason = (
                        "authorized discount percentage required within manager limit"
                    )
                else:
                    for i in eligible:
                        allocations[i] = rounded_div(gross[i] * override_bps, 10000)
            else:
                reason = "unsupported discount rule"
            cap = disc.get("max_discount_paise")
            if cap is not None and sum(allocations) > int(cap):
                allocations = list(_allocate(int(cap), eligible, allocations))
        preliminary[oid] = (row, tuple(allocations), reason)
        if not reason and sum(allocations):
            candidates.append(oid)
    # Evaluate a stackable group (ordered by priority) using remaining line balances.
    stack_ids = [oid for oid in candidates if preliminary[oid][0].get("stackable")]
    stack_discounts = [0] * len(lines)
    stack_applied = {}
    for oid in stack_ids:
        proposed = preliminary[oid][1]
        applied = tuple(
            min(max(0, gross[i] - stack_discounts[i]), x)
            for i, x in enumerate(proposed)
        )
        if any(applied):
            stack_applied[oid] = applied
            stack_discounts = [a + b for a, b in zip(stack_discounts, applied)]
    # Alternative: select a single highest-priority non-stackable offer.
    exclusive = next(
        (oid for oid in candidates if not preliminary[oid][0].get("stackable")), None
    )
    exclusive_alloc = (
        preliminary[exclusive][1] if exclusive else tuple([0] * len(lines))
    )
    choose_exclusive = bool(exclusive and sum(exclusive_alloc) > sum(stack_discounts))
    chosen = {exclusive: exclusive_alloc} if choose_exclusive else stack_applied
    decisions = []
    for row in sorted(offers, key=lambda r: (int(r["priority"]), str(r["offer_id"]))):
        oid = str(row["offer_id"])
        _, proposed, reason = preliminary[oid]
        alloc = chosen.get(oid, tuple([0] * len(lines)))
        if not any(alloc):
            reason = reason or (
                "conflicts with better eligible offer combination"
                if proposed
                else "no discount available"
            )
        decisions.append(
            OfferDecision(oid, any(alloc), sum(alloc), reason or "applied", alloc)
        )
    discounts = tuple(
        sum(d.allocations_paise[i] for d in decisions) for i in range(len(lines))
    )
    assert all(a <= b for a, b in zip(discounts, gross))
    return OfferResult(tuple(decisions), discounts)
