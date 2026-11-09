from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.roster import RosterStatus
from app.schemas.common import UTCDateTime
from app.schemas.reference import ShiftStatusOut


class RosterCreate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class RosterSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    month: int
    version: int
    status: RosterStatus
    created_at: UTCDateTime
    published_at: UTCDateTime | None


class RosterDay(BaseModel):
    date: date
    day: int
    weekday: int
    weekday_label: str
    is_weekend: bool
    holiday: str | None = None


class RosterEmployee(BaseModel):
    id: int
    employee_code: str
    full_name: str


class AssignmentOut(BaseModel):
    employee_id: int
    date: date
    status_code: str
    note: str | None = None


class AssignmentUpdate(BaseModel):
    employee_id: int
    date: date
    status_code: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8)
    ]
    note: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=255)] = None

    @field_validator("note")
    @classmethod
    def blank_note_is_none(cls, value: str | None) -> str | None:
        return value or None


class AssignmentsPatch(BaseModel):
    assignments: list[AssignmentUpdate] = Field(min_length=1, max_length=5000)


class RosterGrid(BaseModel):
    id: int
    year: int
    month: int
    version: int
    status: RosterStatus
    days: list[RosterDay]
    employees: list[RosterEmployee]
    statuses: list[ShiftStatusOut]
    assignments: list[AssignmentOut]
    updated_at: UTCDateTime
    published_at: UTCDateTime | None


class Shortage(BaseModel):
    date: date
    status_code: str
    required: int
    assigned: int


class GenerationResult(BaseModel):
    roster: RosterGrid
    shortages: list[Shortage]
    warnings: list[str]


class Message(BaseModel):
    detail: str
