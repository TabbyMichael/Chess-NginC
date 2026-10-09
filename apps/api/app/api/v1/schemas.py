"""HTTP request/response schemas for API v1 (SEC-016: safe error shapes)."""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """Registration payload."""

    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=256)


class LoginRequest(BaseModel):
    """Login payload."""

    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    """Public user representation (never includes password hash)."""

    id: int
    email: str


class ErrorResponse(BaseModel):
    """Consistent error envelope (SEC-016)."""

    detail: str
