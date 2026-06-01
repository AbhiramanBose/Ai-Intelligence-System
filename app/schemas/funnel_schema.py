from pydantic import BaseModel


class FunnelStage(BaseModel):
    stage: str
    count: int
    dropoff_percent: float


class FunnelResponse(BaseModel):
    store_id: str
    funnel: list[FunnelStage]
