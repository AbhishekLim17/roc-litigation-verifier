from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app import __version__
from app.config import Settings, get_settings
from app.database.session import database_is_reachable
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


def get_database_check() -> Callable[[], bool]:
    """Indirection so tests can swap in a fake database check."""
    return database_is_reachable


@router.get("/health", response_model=HealthResponse)
def health(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    check_database: Annotated[Callable[[], bool], Depends(get_database_check)],
) -> HealthResponse:
    database_ok = check_database()
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        version=__version__,
        environment=settings.app_env,
        database="ok" if database_ok else "unavailable",
        roc_provider=settings.roc_provider,
    )
