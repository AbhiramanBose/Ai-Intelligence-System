from pydantic import BaseModel


class HeatmapZone(BaseModel):
    zone_id: str
    visit_count: int
    avg_dwell_ms: float
    heat_score: int
    data_confidence: str


class HeatmapResponse(BaseModel):
    store_id: str
    zones: list[HeatmapZone]
