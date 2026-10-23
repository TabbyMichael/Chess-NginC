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


class ForgotPasswordRequest(BaseModel):
    """Password-reset request (email only)."""

    email: str = Field(max_length=255)


class ResetPasswordRequest(BaseModel):
    """Password-reset completion payload."""

    token: str = Field(min_length=16, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class GoogleLoginRequest(BaseModel):
    """Google Sign-In payload: the ID token from Google Identity Services."""

    credential: str = Field(min_length=16, max_length=8192)


class MessageResponse(BaseModel):
    """Neutral operational message (never leaks account existence)."""

    message: str


class UserResponse(BaseModel):
    """Public user representation (never includes password hash)."""

    id: int
    email: str
    points: int


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


class AchievementResponse(BaseModel):
    """One catalog entry (ACH-005)."""

    key: str
    title: str
    description: str
    metric: str
    threshold: int
    tier: str  # bronze|silver|gold|diamond|legendary
    group: str  # play|result|points|tactics|pieces|endurance|habit|review|engine|mode


class GameResponse(BaseModel):
    """A game with its move history (API-006/007)."""

    id: int
    mode: str
    status: str
    fen: str
    version: int
    moves: list[MoveResponse] = Field(default_factory=list)
    # Online games only: the color seats. The frontend derives "am I White?"
    # from white_user_id === me.id, never a per-request echoed flag (§8).
    white_user_id: int | None = None
    black_user_id: int | None = None
    # Achievements unlocked by this action (ACH-006); empty for reads.
    unlocked_achievements: list[AchievementResponse] = Field(default_factory=list)


class AchievementProgressResponse(AchievementResponse):
    """A catalog entry as seen by one player: progress plus unlock state."""

    value: int = 0
    unlocked: bool = False
    progress: float = 0.0  # 0..1 toward the threshold
    unlocked_at: str | None = None


class AchievementListResponse(BaseModel):
    """The gallery payload: whole catalog with per-player progress."""

    total: int
    unlocked: int
    items: list[AchievementProgressResponse] = Field(default_factory=list)


class AchievementSeenRequest(BaseModel):
    """Celebration acknowledgement (ACH-007): stop replaying these toasts."""

    keys: list[str] = Field(default_factory=list)


class QueueResponse(BaseModel):
    """Lobby queue state (online-plan §5)."""

    status: str  # 'idle' | 'queued' | 'matched'
    game_id: int | None = None
    color: str | None = None  # 'w' | 'b' when matched


class ReviewRequest(BaseModel):
    """Review generation payload (REVIEW-001)."""

    force: bool = False  # re-analyze even when a stored review exists


class ReviewMoveResponse(BaseModel):
    """One classified ply with its engine facts and coaching line."""

    ply: int
    move_number: int
    uci: str
    san: str
    # Position the move was played from, so the page can render a board per ply.
    pre_fen: str = ""
    color: str  # 'w' | 'b'
    quality: str  # brilliant|best|excellent|good|inaccuracy|mistake|blunder
    centipawn_loss: int
    best_uci: str = ""
    eval_cp: int = 0  # after the ply, from the MOVER's perspective
    eval_mate: int | None = None
    explanation: str = ""


class ReviewEvalPoint(BaseModel):
    """One point of the evaluation graph (white's perspective)."""

    ply: int
    cp: int
    mate: int | None = None


class ReviewImprovement(BaseModel):
    """A mistake/blunder the player could have played better."""

    ply: int
    san: str
    color: str
    best_uci: str
    loss_cp: int


class ReviewSummary(BaseModel):
    """Aggregate accuracy per side (0..100) plus ply count."""

    ply_count: int = 0
    accuracy: dict[str, int] = Field(default_factory=dict)


class ReviewResponse(BaseModel):
    """A stored game review, served without re-analysis (REVIEW-005)."""

    id: int
    game_id: int
    status: str  # 'completed' | 'failed'
    provider: str
    depth: int
    hero_color: str
    error: str | None = None
    summary: ReviewSummary = Field(default_factory=ReviewSummary)
    counts: dict[str, int] = Field(default_factory=dict)
    moves: list[ReviewMoveResponse] = Field(default_factory=list)
    eval_graph: list[ReviewEvalPoint] = Field(default_factory=list)
    improvements: list[ReviewImprovement] = Field(default_factory=list)
    # A completed review is itself an achievement milestone (ACH-006).
    unlocked_achievements: list[AchievementResponse] = Field(default_factory=list)
