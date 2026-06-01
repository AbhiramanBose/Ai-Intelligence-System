from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.metrics_schema import MetricsResponse
from app.schemas.funnel_schema import FunnelResponse
from app.schemas.heatmap_schema import HeatmapResponse
from app.schemas.anomaly_schema import AnomalyResponse
from app.services.metrics_service import MetricsService
from app.services.funnel_service import FunnelService
from app.services.heatmap_service import HeatmapService
from app.services.anomaly_service import AnomalyService

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("/{store_id}/metrics", response_model=MetricsResponse)
def get_metrics(store_id: str, db: Session = Depends(get_db)):
    return MetricsService(db).get_metrics(store_id)


@router.get("/{store_id}/funnel", response_model=FunnelResponse)
def get_funnel(store_id: str, db: Session = Depends(get_db)):
    return FunnelService(db).get_funnel(store_id)


@router.get("/{store_id}/heatmap", response_model=HeatmapResponse)
def get_heatmap(store_id: str, db: Session = Depends(get_db)):
    return HeatmapService(db).get_heatmap(store_id)


@router.get("/{store_id}/anomalies", response_model=AnomalyResponse)
def get_anomalies(store_id: str, db: Session = Depends(get_db)):
    return AnomalyService(db).get_anomalies(store_id)
