from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models import AuditLog, UserRole, UserSession
from tests.conftest import TEST_PASSWORD


def login(client, email="analyst@example.com", password=TEST_PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def actions(db_session):
    return [a.action for a in db_session.scalars(select(AuditLog).order_by(AuditLog.created_at))]


def test_login_sets_httponly_cookie_and_returns_csrf_token(db_client, make_user):
    make_user()

    response = login(db_client)

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "analyst@example.com"
    assert body["user"]["role"] == "analyst"
    assert len(body["csrf_token"]) > 20
    cookie = response.headers["set-cookie"]
    assert "roc_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "password_hash" not in response.text


def test_login_is_case_insensitive_for_email(db_client, make_user):
    make_user()
    assert login(db_client, email="  Analyst@Example.COM ").status_code == 200


def test_session_token_is_stored_hashed(db_client, make_user, db_session):
    make_user()
    response = login(db_client)
    token = response.cookies["roc_session"]

    stored = db_session.scalar(select(UserSession))
    assert stored.token_hash != token
    assert len(stored.token_hash) == 64


def test_wrong_password_and_unknown_email_get_the_same_answer(db_client, make_user, db_session):
    make_user()

    wrong = login(db_client, password="Wrong-Password-1")
    unknown = login(db_client, email="nobody@example.com")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert actions(db_session).count("auth.login_failed") == 2


def test_account_locks_after_repeated_failures(db_client, make_user):
    make_user()
    for _ in range(5):
        login(db_client, password="Wrong-Password-1")

    # Even the correct password is refused while locked.
    assert login(db_client).status_code == 401


def test_inactive_user_cannot_log_in(db_client, make_user):
    make_user(is_active=False)
    assert login(db_client).status_code == 401


def test_me_requires_login(db_client):
    assert db_client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_user_and_csrf_token(db_client, make_user):
    make_user(role=UserRole.REVIEWER)
    csrf = login(db_client).json()["csrf_token"]

    response = db_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "reviewer"
    assert response.json()["csrf_token"] == csrf


def test_logout_requires_csrf_token(db_client, make_user):
    make_user()
    login(db_client)

    response = db_client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert db_client.get("/api/v1/auth/me").status_code == 200  # still signed in


def test_logout_revokes_session(db_client, make_user, db_session):
    make_user()
    csrf = login(db_client).json()["csrf_token"]
    old_cookie = db_client.cookies["roc_session"]

    response = db_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 204
    # Replaying the old cookie must not work after logout.
    db_client.cookies.set("roc_session", old_cookie)
    assert db_client.get("/api/v1/auth/me").status_code == 401
    assert actions(db_session)[-1] == "auth.logout"


def test_idle_session_expires(db_client, make_user, db_session):
    make_user()
    login(db_client)
    stored = db_session.scalar(select(UserSession))
    stored.last_seen_at = datetime.now(UTC) - timedelta(hours=2)
    db_session.flush()

    assert db_client.get("/api/v1/auth/me").status_code == 401


def test_login_is_audited(db_client, make_user, db_session):
    make_user()
    login(db_client)
    assert "auth.login" in actions(db_session)


def test_audit_log_is_append_only(db_session, make_user):
    user = make_user()
    db_session.add(AuditLog(action="test.event", actor_user_id=user.id, details={}))
    db_session.flush()

    with pytest.raises(DBAPIError, match="append-only"), db_session.begin_nested():
        db_session.execute(text("UPDATE audit_logs SET action = 'tampered'"))
    with pytest.raises(DBAPIError, match="append-only"), db_session.begin_nested():
        db_session.execute(text("DELETE FROM audit_logs"))
