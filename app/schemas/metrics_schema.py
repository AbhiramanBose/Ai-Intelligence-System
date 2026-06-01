from pydantic import BaseModel


class MetricsResponse(BaseModel):
    store_id: str
    unique_visitors: int
    conversion_rate: float
    avg_dwell_per_zone: dict[str, float]
    current_queue_depth: int
    abandonment_rate: float
