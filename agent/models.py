"""Pydantic data models shared by every step of the agent."""
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Appointment(BaseModel):
    patient_id: str
    name: str
    dob: date
    payer: str
    member_id: str
    appt_date: date
    cdt_codes: list[str]

    @field_validator("cdt_codes", mode="before")
    @classmethod
    def split_codes(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [c.strip() for c in v.split(";") if c.strip()]
        return v


class FeeItem(BaseModel):
    cdt_code: str
    description: str
    category: Literal["preventive", "basic", "major"]
    fee: float
    frequency_group: str | None = None

    @field_validator("frequency_group", mode="before")
    @classmethod
    def blank_is_none(cls, v: Any) -> Any:
        return v or None


class FieldValue(BaseModel):
    """One benefits field plus where it came from and how sure we are."""
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    source: str


class LineEstimate(BaseModel):
    cdt_code: str
    fee: float
    covered: bool
    insurance: float
    patient: float
    note: str = ""


class Estimate(BaseModel):
    lines: list[LineEstimate]

    @property
    def patient_total(self) -> float:
        return round(sum(line.patient for line in self.lines), 2)

    @property
    def insurance_total(self) -> float:
        return round(sum(line.insurance for line in self.lines), 2)


class VerificationResult(BaseModel):
    appointment: Appointment
    status: Literal["VERIFIED", "NEEDS_REVIEW"]
    reasons: list[str]
    sources: list[str]
    fields: dict[str, FieldValue]
    estimate: Estimate
