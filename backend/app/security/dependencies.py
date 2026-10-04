from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_db
from app.models import User, UserRole, UserSession
from app.security.sessions import csrf_tokens_match, get_active_session

CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_current_session(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserSession:
    """Require a valid login session; on state-changing requests also require the CSRF token."""
    token = request.cookies.get(settings.session_cookie_name)
    record = get_active_session(db, token, settings) if token else None
    if record is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    if request.method not in _SAFE_METHODS and not csrf_tokens_match(
        record.csrf_token, request.headers.get(CSRF_HEADER)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing or invalid CSRF token")
    db.commit()  # persist the refreshed idle timer
    return record


def get_current_user(session: Annotated[UserSession, Depends(get_current_session)]) -> User:
    return session.user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return checker


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
