from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.user import Role


class LoginRequest(BaseModel):
    identifier: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    email: str
    role: Role
    employee_id: int | None
    full_name: str | None = None
    employee_code: str | None = None


class LoginResponse(BaseModel):
    user: UserOut
    csrf_token: str


class MeResponse(BaseModel):
    user: UserOut
    csrf_token: str
