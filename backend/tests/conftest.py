from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.routes.health import get_database_check
from app.main import create_app


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
def fake_database(app):
    """Replace the real database check. Set `.reachable` to control the result."""

    class FakeDatabase:
        reachable = True

    fake = FakeDatabase()
    app.dependency_overrides[get_database_check] = lambda: lambda: fake.reachable
    return fake
