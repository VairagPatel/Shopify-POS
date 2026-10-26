"""Exact money conversion shared by sale, refund and reporting workflows."""

from decimal import Decimal
from app.constants import PAISE_PER_RUPEE


# Format integer paise as a decimal currency string at an integration boundary.
def money(amount_paise):
    return f"{amount_paise // PAISE_PER_RUPEE}.{amount_paise % PAISE_PER_RUPEE:02d}"


# Convert source currency values through Decimal rather than binary floating point.
def paise(amount):
    return int(Decimal(str(amount)) * PAISE_PER_RUPEE)
