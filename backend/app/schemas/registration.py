import uuid

from pydantic import BaseModel, EmailStr, Field


class RegistrationRequest(BaseModel):
    organization_name: str = Field(
        min_length=2,
        max_length=150,
    )

    organization_slug: str = Field(
        min_length=2,
        max_length=150,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    full_name: str = Field(
        min_length=2,
        max_length=150,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class RegistrationResponse(BaseModel):
    organization_id: uuid.UUID
    user_id: uuid.UUID
    membership_id: uuid.UUID
    role: str
    message: str