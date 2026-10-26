"""Tax calculation in integer paise using effective-dated HSN configuration."""

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Sequence
from app.constants import BASIS_POINTS_PER_UNIT


# Round a nonnegative integer ratio using half-up money semantics.
def rounded_div(numerator: int, denominator: int) -> int:
    "Round a nonnegative integer ratio using half-up money semantics."
    if numerator < 0 or denominator <= 0:
        raise ValueError("Expected non-negative numerator and positive denominator")
    return (2 * numerator + denominator) // (2 * denominator)


@dataclass(frozen=True)
class TaxLine:
    hsn: str
    quantity: int
    gross_paise: int
    discount_paise: int
    total_paise: int
    taxable_paise: int
    cgst_paise: int
    sgst_paise: int
    rate_bps: int


class TaxCatalog:
    # Initialize the adapter or service with its explicit dependencies.
    def __init__(self, rows: Sequence[Mapping]):
        "Initialize the adapter or service with its explicit dependencies."
        self.rows = tuple(rows)

    # Require exactly one effective HSN rate for the billing date.
    def rate_for(self, hsn: str, on_date: date) -> int:
        "Require exactly one effective HSN rate for the billing date."
        candidates = [
            row
            for row in self.rows
            if str(row["hsn"]) == str(hsn)
            and date.fromisoformat(row["effective_from"]) <= on_date
            and (
                not row.get("effective_to")
                or on_date <= date.fromisoformat(row["effective_to"])
            )
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"Expected exactly one active GST rate for HSN {hsn} on {on_date}; found {len(candidates)}"
            )
        rate = int(candidates[0]["rate_bps"])
        if rate < 0 or rate > BASIS_POINTS_PER_UNIT:
            raise ValueError("GST rate out of range")
        return rate


# Split discounted GST-inclusive MRP into taxable value and exact tax halves.
def inclusive_tax_line(
    *,
    hsn: str,
    quantity: int,
    unit_price_paise: int,
    discount_paise: int,
    rate_bps: int,
) -> TaxLine:
    "Split discounted GST-inclusive MRP into taxable value and exact tax halves."
    if quantity <= 0 or unit_price_paise < 0 or rate_bps < 0:
        raise ValueError("Invalid price, quantity, or rate")
    gross = quantity * unit_price_paise
    if not 0 <= discount_paise <= gross:
        raise ValueError("Discount cannot exceed line gross")
    total = gross - discount_paise
    taxable = rounded_div(
        total * BASIS_POINTS_PER_UNIT, BASIS_POINTS_PER_UNIT + rate_bps
    )
    tax = total - taxable
    cgst = rounded_div(tax, 2)
    sgst = tax - cgst  # ensure exact paisa reconciliation on odd tax amounts
    assert taxable + cgst + sgst == total
    return TaxLine(
        hsn, quantity, gross, discount_paise, total, taxable, cgst, sgst, rate_bps
    )


# Aggregate line amounts without converting money to floating point.
def invoice_totals(lines: Sequence[TaxLine]) -> dict[str, int]:
    "Aggregate line amounts without converting money to floating point."
    return {
        name: sum(getattr(x, name) for x in lines)
        for name in (
            "gross_paise",
            "discount_paise",
            "total_paise",
            "taxable_paise",
            "cgst_paise",
            "sgst_paise",
        )
    }
