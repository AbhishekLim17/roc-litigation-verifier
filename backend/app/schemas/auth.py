import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import UserRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole


class SessionOut(BaseModel):
    user: UserOut
    # The frontend keeps this in memory and sends it back in the X-CSRF-Token header.
    csrf_token: str
