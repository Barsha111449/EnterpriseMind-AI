import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


EmployeeRole = Literal[
    "admin",
    "manager",
    "employee",
    "reviewer",
]


class EmployeeCreateRequest(BaseModel):
    """Information required to create an employee account."""

    full_name: str = Field(
        min_length=2,
        max_length=150,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    role: EmployeeRole = "employee"


class EmployeeRoleUpdateRequest(BaseModel):
    """New role assigned to an employee."""

    role: EmployeeRole


class EmployeeStatusUpdateRequest(BaseModel):
    """Activate or deactivate an employee account."""

    is_active: bool


class EmployeeResponse(BaseModel):
    """One employee belonging to the current organization."""

    user_id: uuid.UUID
    membership_id: uuid.UUID
    organization_id: uuid.UUID

    email: str
    full_name: str
    role: str
    is_active: bool

    user_created_at: datetime
    joined_at: datetime