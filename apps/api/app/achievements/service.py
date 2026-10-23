"""Achievement evaluation service (ACH-005/006/007).

Compares a player's stats against the catalog and persists the difference.
Catalog rows never live in the database, so a brand-new achievement simply
starts unlocking for players as soon as it is added here.

Two entry points matter to the rest of the app:

* ``flush`` — called after game/review transitions; returns the achievements
  unlocked *since the last call* so they can ride back in the response and be
  celebrated once.
* ``gallery`` — the full catalog with per-player progress (locked tiles show
  how close the player is).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.achievements.catalog import CATALOG, Achievement
from app.achievements.stats import compute_stats
from app.models.user_achievement import UserAchievement

# Catalog keys by metric, so evaluation touches each stat once.
_BY_METRIC: dict[str, list[Achievement]] = {}
for _achievement in CATALOG:
    _BY_METRIC.setdefault(_achievement.metric, []).append(_achievement)


@dataclass(frozen=True)
class Progress:
    """One catalog entry as seen by one player."""

    achievement: Achievement
    value: int
    unlocked: bool
    unlocked_at: datetime | None = None
    seen_at: datetime | None = None

    @property
    def ratio(self) -> float:
        """0..1 completion toward the threshold (1.0 once unlocked)."""
        if self.unlocked:
            return 1.0
        threshold = self.achievement.threshold
        if threshold <= 0:
            return 1.0
        return max(0.0, min(1.0, self.value / threshold))


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def earned_keys(stats: dict[str, int]) -> set[str]:
    """Catalog keys whose threshold the current stats satisfy."""
    out: set[str] = set()
    for metric, achievements in _BY_METRIC.items():
        value = int(stats.get(metric, 0))
        for achievement in achievements:
            if value >= achievement.threshold:
                out.add(achievement.key)
    return out


def _stored(db: Session, user_id: int) -> dict[str, UserAchievement]:
    rows = db.execute(select(UserAchievement).where(UserAchievement.user_id == user_id)).scalars()
    return {row.key: row for row in rows}


def flush(db: Session, user_id: int) -> list[Achievement]:
    """Persist any newly earned achievements and return them (in catalog order).

    Idempotent: a second call with no new stats records nothing and returns an
    empty list, so it is safe on every game transition.
    """
    stored = _stored(db, user_id)
    if len(stored) >= len(CATALOG):
        return []  # everything is already unlocked

    new_keys = earned_keys(compute_stats(db, user_id)) - stored.keys()
    if not new_keys:
        return []

    now = _utcnow()
    unlocked: list[Achievement] = []
    for achievement in CATALOG:  # catalog order keeps the celebration stable
        if achievement.key in new_keys:
            db.add(
                UserAchievement(user_id=user_id, key=achievement.key, unlocked_at=now, seen_at=None)
            )
            unlocked.append(achievement)
    db.commit()
    return unlocked


def gallery(db: Session, user_id: int) -> list[Progress]:
    """Full catalog with this player's progress, unlocked entries first."""
    stats = compute_stats(db, user_id)
    stored = _stored(db, user_id)
    entries = [
        Progress(
            achievement=achievement,
            value=int(stats.get(achievement.metric, 0)),
            unlocked=achievement.key in stored,
            unlocked_at=stored[achievement.key].unlocked_at if achievement.key in stored else None,
            seen_at=stored[achievement.key].seen_at if achievement.key in stored else None,
        )
        for achievement in CATALOG
    ]
    entries.sort(
        key=lambda item: (not item.unlocked, item.achievement.tier.value, item.achievement.key)
    )
    return entries


def pending(db: Session, user_id: int) -> list[Achievement]:
    """Unlocked-but-not-yet-celebrated achievements (used on page load)."""
    flush(db, user_id)
    rows = db.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == user_id, UserAchievement.seen_at.is_(None))
        .order_by(UserAchievement.unlocked_at, UserAchievement.id)
    ).scalars()
    by_key = {a.key: a for a in CATALOG}
    return [by_key[row.key] for row in rows if row.key in by_key]


def mark_seen(db: Session, user_id: int, keys: list[str]) -> int:
    """Acknowledge celebrations so they are not replayed. Returns the count."""
    if not keys:
        return 0
    now = _utcnow()
    rows = db.execute(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.key.in_(keys),
            UserAchievement.seen_at.is_(None),
        )
    ).scalars()
    updated = 0
    for row in rows:
        row.seen_at = now
        updated += 1
    if updated:
        db.commit()
    return updated
