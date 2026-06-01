from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.event import Event


class HealthService:
    def __init__(self, db: Session):
        self.db = db

    def get_health(self) -> dict:
        rows = (
            self.db.query(Event.store_id, func.max(Event.timestamp))
            .group_by(Event.store_id)
            .all()
        )
        last_by_store = {store_id: (ts.isoformat() if ts else None) for store_id, ts in rows}
        warnings = []
        now = datetime.now(timezone.utc)
        for store_id, ts in rows:
            if ts:
                ts_aware = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
                if now - ts_aware > timedelta(minutes=10):
                    warnings.append({
                        "type": "STALE_FEED",
                        "store_id": store_id,
                        "message": "Last event is older than 10 minutes.",
                    })
        return {
            "status": "degraded" if warnings else "ok",
            "database": "connected",
            "last_event_timestamp_by_store": last_by_store,
            "warnings": warnings,
        }
