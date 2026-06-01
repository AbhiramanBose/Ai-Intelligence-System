from pydantic import BaseModel


class AnomalyItem(BaseModel):
    type: str
    severity: str
    message: str
    suggested_action: str


class AnomalyResponse(BaseModel):
    store_id: str
    anomalies: list[AnomalyItem]
