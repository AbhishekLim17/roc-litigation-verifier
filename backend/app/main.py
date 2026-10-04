import logging

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app import __version__
from app.api.router import api_router
from app.config import get_settings

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Interactive API docs are handy in development but are not exposed in production.
    docs_enabled = settings.is_development
    app = FastAPI(
        title="ROC Litigation Verification API",
        version=__version__,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
    )

    @app.middleware("http")
    async def add_security_headers(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    app.include_router(api_router)
    return app


app = create_app()
