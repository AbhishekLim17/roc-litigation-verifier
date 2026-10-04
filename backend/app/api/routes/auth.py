from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_db
from app.models import User, UserSession
from app.schemas.auth import LoginRequest, SessionOut, UserOut
from app.security.dependencies import client_ip, get_current_session
from app.security.passwords import verify_password
from app.security.sessions import create_session, revoke_session
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])

# One message for every failure, so responses don't reveal which emails exist.
INVALID_LOGIN = "Invalid email or password"


@router.post("/login", response_model=SessionOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionOut:
    ip = client_ip(request)
    now = datetime.now(UTC)
    user = db.scalar(select(User).where(User.email == payload.email))

    if user is not None and user.locked_until is not None and user.locked_until > now:
        record_audit(db, "auth.login_blocked", actor_user_id=user.id, ip_address=ip)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)

    password_ok = verify_password(payload.password, user.password_hash if user else None)
    if user is None or not password_ok or not user.is_active:
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_max_failed_attempts:
                user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
                user.failed_login_count = 0
        record_audit(
            db,
            "auth.login_failed",
            actor_user_id=user.id if user else None,
            details={"email": payload.email},
            ip_address=ip,
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    issued = create_session(db, user, settings, ip, request.headers.get("user-agent"))
    record_audit(db, "auth.login", actor_user_id=user.id, ip_address=ip)
    db.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=issued.token,
        max_age=settings.session_absolute_timeout_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api",
    )
    return SessionOut(user=UserOut.model_validate(user), csrf_token=issued.record.csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    revoke_session(session)
    record_audit(db, "auth.logout", actor_user_id=session.user_id, ip_address=client_ip(request))
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(settings.session_cookie_name, path="/api")
    return response


@router.get("/me", response_model=SessionOut)
def me(session: Annotated[UserSession, Depends(get_current_session)]) -> SessionOut:
    return SessionOut(user=UserOut.model_validate(session.user), csrf_token=session.csrf_token)
