import pytest
from sqlalchemy import create_engine

from app import __version__
from app.database.session import database_is_reachable, get_engine


def test_health_ok_when_database_reachable(client, fake_database):
    fake_database.reachable = True

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": __version__,
        "environment": "development",
        "database": "ok",
        "roc_provider": "mock",
    }


def test_health_degraded_when_database_unreachable(client, fake_database):
    fake_database.reachable = False

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"


def test_security_headers_present(client, fake_database):
    response = client.get("/api/v1/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_database_check_returns_false_instead_of_raising():
    # Port 1 is never a Postgres server, so this fails fast without network access.
    engine = create_engine(
        "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none",
        connect_args={"connect_timeout": 1},
    )
    assert database_is_reachable(engine) is False


@pytest.mark.db
def test_real_database_is_reachable():
    if not database_is_reachable(get_engine()):
        pytest.skip("PostgreSQL is not running; start it with `docker compose up -d db`")
    assert database_is_reachable(get_engine()) is True
