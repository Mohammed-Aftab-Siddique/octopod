from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ShiftStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    label: str
    color: str
    text_color: str
    is_working: bool
    sort_order: int


class StaffingRequirementIn(BaseModel):
    status_code: str = Field(min_length=1, max_length=8)
    required_count: int = Field(ge=0, le=10_000)


class StaffingRequirementsPut(BaseModel):
    requirements: list[StaffingRequirementIn]


class StaffingRequirementOut(BaseModel):
    status_code: str
    required_count: int


class HolidayCreate(BaseModel):
    date: date
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class HolidayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    label: str
