from pydantic import BaseModel


class HealthWarning(BaseModel):
    type: str
    store_id: str | None = None
    message: str


class HealthResponse(BaseModel):
    status: str
    database: str
    last_event_timestamp_by_store: dict[str, str | None]
    warnings: list[HealthWarning]
