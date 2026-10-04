import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import User, UserSession


@dataclass(frozen=True)
class IssuedSession:
    token: str  # goes into the httpOnly cookie, never stored server-side
    record: UserSession


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def create_session(
    db: Session,
    user: User,
    settings: Settings,
    ip_address: str | None,
    user_agent: str | None,
) -> IssuedSession:
    token = secrets.token_urlsafe(32)
    now = _now()
    record = UserSession(
        token_hash=_hash_token(token),
        csrf_token=secrets.token_urlsafe(32),
        user_id=user.id,
        expires_at=now + timedelta(hours=settings.session_absolute_timeout_hours),
        last_seen_at=now,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:300] or None,
    )
    db.add(record)
    db.flush()
    return IssuedSession(token=token, record=record)


def get_active_session(db: Session, token: str, settings: Settings) -> UserSession | None:
    """Return the session if it is valid, refreshing its idle timer; otherwise None."""
    record = db.scalar(select(UserSession).where(UserSession.token_hash == _hash_token(token)))
    if record is None or record.revoked_at is not None:
        return None
    now = _now()
    idle_limit = record.last_seen_at + timedelta(minutes=settings.session_idle_timeout_minutes)
    if now >= record.expires_at or now >= idle_limit or not record.user.is_active:
        return None
    record.last_seen_at = now
    return record


def revoke_session(record: UserSession) -> None:
    record.revoked_at = _now()


def csrf_tokens_match(expected: str, provided: str | None) -> bool:
    return provided is not None and secrets.compare_digest(expected, provided)
