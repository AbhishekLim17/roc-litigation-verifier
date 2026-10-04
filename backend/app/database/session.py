import logging
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
    )


def database_is_reachable(engine: Engine | None = None) -> bool:
    """Return True if a trivial query succeeds. Never raises."""
    try:
        with (engine or get_engine()).connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        # Log the exception type only: driver messages can include the connection string.
        logger.warning("Database health check failed: %s", type(exc).__name__)
        return False
