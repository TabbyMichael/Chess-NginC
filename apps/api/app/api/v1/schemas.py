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


class CreateGameRequest(BaseModel):
    """Game creation payload (API-005)."""

    mode: str = Field(default="local", max_length=50)


class MoveRequest(BaseModel):
    """Move submission payload (API-008/019)."""

    uci: str = Field(min_length=4, max_length=10)
    expected_version: int = Field(ge=1)


class VersionRequest(BaseModel):
    """Payload for version-guarded actions (API-009/012)."""

    expected_version: int = Field(ge=1)


class EngineMoveRequest(BaseModel):
    """Engine move payload with optional search budget (API-012)."""

    expected_version: int = Field(ge=1)
    max_depth: int | None = Field(default=None, ge=1, le=6)
    max_time_ms: int | None = Field(default=None, ge=100, le=3000)


class MoveResponse(BaseModel):
    """A stored move."""

    uci: str
    san: str
    move_number: int


class GameResponse(BaseModel):
    """A game with its move history (API-006/007)."""

    id: int
    mode: str
    status: str
    fen: str
    version: int
    moves: list[MoveResponse] = Field(default_factory=list)
