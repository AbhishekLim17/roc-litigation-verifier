from typing import Literal

from pydantic import BaseModel

ComponentStatus = Literal["ok", "unavailable"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: ComponentStatus
    roc_provider: str
