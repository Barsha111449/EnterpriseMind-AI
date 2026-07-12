import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    organization_slug: str = Field(
        min_length=2,
        max_length=150,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str


class CurrentUserResponse(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    role: str