"""One canonical Indian mobile-number representation at application boundaries."""

import re
from typing import Annotated
from pydantic import BeforeValidator, Field
from app.constants import (
    INDIAN_COUNTRY_CODE,
    INDIAN_PHONE_PREFIX,
    MOBILE_DIGIT_COUNT,
    MAX_PHONE_INPUT_LENGTH,
)


# Accept common Indian entry formats without guessing a country or stripping arbitrary text.
def normalize_phone(value):
    """Return +91 plus ten mobile digits; reject malformed and foreign numbers."""
    if not isinstance(value, str) or len(value) > MAX_PHONE_INPUT_LENGTH:
        raise ValueError("Enter an Indian mobile number as text")
    value = value.strip()
    if not re.fullmatch(r"[+0-9 ()-]+", value, flags=re.ASCII):
        raise ValueError("Use digits with an optional +91 prefix")
    compact = re.sub(r"[ ()-]", "", value)
    if compact.startswith(INDIAN_PHONE_PREFIX):
        local = compact[len(INDIAN_PHONE_PREFIX) :]
    elif len(compact) == MOBILE_DIGIT_COUNT + len(
        INDIAN_COUNTRY_CODE
    ) and compact.startswith(INDIAN_COUNTRY_CODE):
        local = compact[len(INDIAN_COUNTRY_CODE) :]
    elif len(compact) == MOBILE_DIGIT_COUNT + 1 and compact.startswith("0"):
        local = compact[1:]
    else:
        local = compact
    if not re.fullmatch(r"[6-9][0-9]{9}", local, flags=re.ASCII):
        raise ValueError("Enter ten Indian mobile digits, optionally prefixed with +91")
    return INDIAN_PHONE_PREFIX + local


PhoneNumber = Annotated[
    str,
    BeforeValidator(normalize_phone),
    Field(
        description="Indian mobile number. Accepts 9000000005, 919000000005, 09000000005 or +91 90000 00005; normalized to +919000000005.",
        examples=["+919000000005"],
    ),
]
