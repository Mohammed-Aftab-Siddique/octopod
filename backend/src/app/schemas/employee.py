from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.schemas.common import UTCDateTime

EmployeeCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
EmployeeName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
OptionalEmployeeCode = Annotated[
    str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]
OptionalEmployeeName = Annotated[
    str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
ShiftCode = Annotated[
    str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=8)
]


class EmployeeCreate(BaseModel):
    employee_code: EmployeeCode
    full_name: EmployeeName
    email: EmailStr
    rotation_offset: int | None = Field(default=None, ge=0)
    default_shift: ShiftCode = None
    password: str | None = Field(default=None, min_length=8, max_length=200)


class EmployeeUpdate(BaseModel):
    employee_code: OptionalEmployeeCode = None
    full_name: OptionalEmployeeName = None
    email: EmailStr | None = None
    rotation_offset: int | None = Field(default=None, ge=0)
    default_shift: ShiftCode = None
    is_active: bool | None = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str
    full_name: str
    email: str
    is_active: bool
    rotation_offset: int
    default_shift: str | None
    created_at: UTCDateTime


class EmployeeLookupOut(BaseModel):
    employee_code: str
    full_name: str


class PasswordResetRequest(BaseModel):
    password: str = Field(min_length=8, max_length=200)
