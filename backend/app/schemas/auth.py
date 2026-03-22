from datetime import datetime

from pydantic import BaseModel, Field, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr = Field(examples=["john@example.com"])
    password: str = Field(min_length=8, examples=["password123"])


class RegisterRequest(BaseModel):
    firstName: str = Field(min_length=1, examples=["John"])
    lastName: str = Field(min_length=1, examples=["Smith"])
    email: EmailStr = Field(examples=["john@example.com"])
    password: str = Field(min_length=8, examples=["password123"])


class GoogleLoginRequest(BaseModel):
    credential: str = Field(examples=["google-oauth-token"])


class UserResponse(BaseModel):
    id: str = Field(examples=["1"])
    email: str = Field(examples=["john@example.com"])
    firstName: str = Field(examples=["John"])
    lastName: str = Field(examples=["Smith"])
    avatarUrl: str | None = Field(default=None, examples=[None])
    createdAt: str = Field(examples=["2025-01-01T00:00:00"])

    model_config = {"from_attributes": True}

    @classmethod
    def from_db(cls, user) -> "UserResponse":
        return cls(
            id=str(user.id),
            email=user.email or "",
            firstName=user.name,
            lastName=user.surname,
            avatarUrl=user.avatar_url,
            createdAt=user.created_at.isoformat() if isinstance(user.created_at, datetime) else str(user.created_at or ""),
        )


class AuthResponse(BaseModel):
    user: UserResponse
    token: str
