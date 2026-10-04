import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog

# Keys that must never be written to the audit log, even by mistake.
_FORBIDDEN_KEYS = {"password", "password_hash", "token", "csrf_token", "cookie", "cookies"}


def record_audit(
    db: Session,
    action: str,
    *,
    actor_user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    clean = {k: v for k, v in (details or {}).items() if k.lower() not in _FORBIDDEN_KEYS}
    entry = AuditLog(
        action=action,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        details=clean,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry
