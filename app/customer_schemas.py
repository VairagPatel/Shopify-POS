"""Explicit customer lookup and clinical input contracts for Swagger and documentation."""

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.phone import PhoneNumber


class CustomerLookupRequest(BaseModel):
    phone: PhoneNumber


class CustomerRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int = Field(
        description="Source customer ID; use as stable identity, not as a phone number."
    )
    phone: PhoneNumber
    first_name: str
    last_name: str
    tags: str = ""


class SourceEyeRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    sph: float | str
    cyl: float | str
    axis: int | None = None
    add: float | str | None = None


class PrescriptionRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    rx_id: str
    customer_id: int
    phone: PhoneNumber
    date: str = Field(
        description="Issued date or timestamp; used when selecting the latest valid prescription."
    )
    valid_until: str
    od: SourceEyeRecord = Field(description="Right eye")
    os: SourceEyeRecord = Field(description="Left eye")


class CustomerLookupResponse(BaseModel):
    customer: CustomerRecord
    prescriptions: list[PrescriptionRecord] = Field(
        description="Source plus locally authored records. Not all are current; sale preparation chooses the latest unexpired record."
    )


class EyeInput(BaseModel):
    sph: Decimal = Field(
        ge=-30, le=30, multiple_of=Decimal("0.25"), description="Sphere in diopters"
    )
    cyl: Decimal = Field(
        ge=-12, le=12, multiple_of=Decimal("0.25"), description="Cylinder in diopters"
    )
    axis: int = Field(strict=True, ge=0, le=180, multiple_of=5)
    add: Decimal = Field(ge=0, le=5, multiple_of=Decimal("0.25"))


class PrescriptionInput(BaseModel):
    phone: PhoneNumber
    store_code: str | None = Field(default=None, description="Store where the clinician entered this prescription; the frontend supplies the selected store.")
    od: EyeInput
    os: EyeInput
    valid_until: date = Field(
        description="Today through two years ahead; validated by the clinical endpoint."
    )
