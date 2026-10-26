"""Pure prescription and variant validation; no external API calls."""

from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence
from app.domain.models import Prescription, LensConfiguration
from app.constants import INDIA


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reasons: tuple[str, ...]


# Reject expired prescriptions and lens choices outside clinical metadata limits.
def validate_lens(
    rx: Prescription, lens: LensConfiguration, metadata: Mapping, *, on_date: date
) -> ValidationResult:
    "Reject expired prescriptions and lens choices outside clinical metadata limits."
    errors = []
    if rx.valid_until < on_date:
        errors.append(
            f"Prescription {rx.prescription_id} expired on {rx.valid_until}; obtain a new eye test"
        )
    if str(metadata.get("line_type")) != "lens":
        errors.append("Selected variant is not a lens")
    for prop, supplied in [("lens_type", lens.lens_type), ("coating", lens.coating)]:
        if str(metadata.get(prop)) != str(supplied):
            errors.append(f"Selected lens {prop} does not match variant catalog")
    try:
        if Decimal(str(metadata.get("index"))) != Decimal(lens.index):
            errors.append("Selected lens index does not match variant catalog")
    except (InvalidOperation, TypeError):
        errors.append("Invalid lens index metadata")
    limits = metadata.get("rx_limits") or {}
    required = ("sph_min", "sph_max", "cyl_abs_max", "add_required")
    if any(k not in limits for k in required):
        errors.append(
            "Lens prescription limits are missing; ask staff to verify catalog"
        )
        return ValidationResult(False, tuple(errors))
    for side, eye in [("right", rx.right), ("left", rx.left)]:
        try:
            sph = Decimal(eye.sphere)
            cyl = Decimal(eye.cylinder)
            lower, upper = (
                Decimal(str(limits["sph_min"])),
                Decimal(str(limits["sph_max"])),
            )
            maximum_cyl = Decimal(str(limits["cyl_abs_max"]))
            if not sph.is_finite() or not cyl.is_finite():
                raise ValueError("nonfinite values")
            if not lower <= sph <= upper:
                errors.append(
                    f"{side} sphere {sph} outside supported {lower} to {upper}; select another lens"
                )
            if abs(cyl) > maximum_cyl:
                errors.append(
                    f"{side} cylinder {cyl} exceeds ±{maximum_cyl}; select another lens"
                )
            if eye.axis is None:
                errors.append(f"{side} axis is required; ask the optometrist to verify")
            elif not 0 <= eye.axis <= 180 or eye.axis % 5:
                errors.append(f"{side} axis must use 5-degree steps from 0 to 180")
            # Progressive and bifocal lenses need a usable ADD. Single-vision
            # prescriptions may legitimately omit ADD, so do not reject them.
            if eye.add is None:
                if limits.get("add_required", False):
                    errors.append(
                        f"{side} ADD is required for this lens; confirm the prescription"
                    )
            elif limits.get("add_required", False):
                add = Decimal(eye.add)
                if not add.is_finite() or not Decimal(
                    str(limits.get("add_min", "0"))
                ) <= add <= Decimal(str(limits.get("add_max", "5"))):
                    errors.append(
                        f"{side} ADD outside supported range; confirm prescription"
                    )
        except (InvalidOperation, ValueError, TypeError, KeyError):
            errors.append(
                f"{side} prescription contains invalid numbers; ask optometrist to verify"
            )
    return ValidationResult(not errors, tuple(errors))


# Select the most recently issued unexpired prescription.
def latest_valid_prescription(
    prescriptions: Sequence[Prescription], *, on_date: date
) -> Prescription | None:
    "Select the most recently issued unexpired prescription."
    valid = [p for p in prescriptions if p.valid_until >= on_date]

    # Normalize legacy date-only records and timezone-aware clinical entries before ordering.
    def issued_order(prescription):
        """Compare mixed source timestamps on one aware timeline without changing Rx values."""
        issued_at = prescription.issued_at or datetime.min
        if issued_at.tzinfo is None:
            issued_at = issued_at.replace(tzinfo=INDIA)
        return issued_at, prescription.prescription_id

    return max(valid, key=issued_order, default=None)
