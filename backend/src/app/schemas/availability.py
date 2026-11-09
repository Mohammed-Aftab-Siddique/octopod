from datetime import date
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.availability import AvailabilityKind
from app.schemas.common import UTCDateTime


class AvailabilityCreate(BaseModel):
    start_date: date
    end_date: date
    kind: AvailabilityKind
    note: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=255)] = None

    @field_validator("note")
    @classmethod
    def blank_note_is_none(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def validate_range(self) -> "AvailabilityCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("availability range cannot exceed 366 days")
        return self


class AvailabilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    date: date
    kind: AvailabilityKind
    note: str | None
    created_at: UTCDateTime
