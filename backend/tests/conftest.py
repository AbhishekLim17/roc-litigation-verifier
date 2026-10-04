from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session

from app.api.routes.health import get_database_check
from app.config import get_settings
from app.database.session import database_is_reachable, get_db
from app.main import create_app
from app.models import User, UserRole
from app.security.passwords import hash_password

TEST_PASSWORD = "Correct-Horse-42"


def _test_database_url() -> URL:
    url = make_url(str(get_settings().database_url))
    return url.set(database=f"{url.database}_test")


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """A separate <db>_test database, recreated and migrated once per test run."""
    test_url = _test_database_url()
    admin_engine = create_engine(
        test_url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 2},
    )
    if not database_is_reachable(admin_engine):
        pytest.skip("PostgreSQL is not running; start it with `docker compose up -d db`")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{test_url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    admin_engine.dispose()

    config = Config("alembic.ini")
    config.attributes["database_url"] = test_url.render_as_string(hide_password=False)
    command.upgrade(config, "head")

    engine = create_engine(test_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """Each test runs inside a transaction that is rolled back afterwards."""
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def app():
    application = create_app()
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_client(app, db_session) -> Iterator[TestClient]:
    """A test client whose requests use the per-test database session."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user(db_session):
    def factory(email="analyst@example.com", role=UserRole.ANALYST, password=TEST_PASSWORD, **kw):
        user = User(
            email=email,
            full_name=kw.pop("full_name", "Test User"),
            role=role,
            password_hash=hash_password(password),
            **kw,
        )
        db_session.add(user)
        db_session.flush()
        return user

    return factory


@pytest.fixture
def fake_database(app):
    """Replace the real database check. Set `.reachable` to control the result."""

    class FakeDatabase:
        reachable = True

    fake = FakeDatabase()
    app.dependency_overrides[get_database_check] = lambda: lambda: fake.reachable
    return fake
