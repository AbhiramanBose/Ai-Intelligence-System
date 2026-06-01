from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.event import Event
from app.services.pos_correlation_service import PosCorrelationService


class HeatmapService:
    def __init__(self, db: Session):
        self.db = db

    def _data_confidence(self, session_count: int) -> str:
        if session_count < 20:
            return "LOW"
        if session_count < 50:
            return "MEDIUM"
        return "HIGH"

    def get_heatmap(self, store_id: str) -> dict:
        events = (
            self.db.query(Event)
            .filter(Event.store_id == store_id, Event.is_staff.is_(False))
            .order_by(Event.timestamp.asc())
            .all()
        )

        correlation = PosCorrelationService(self.db).get_summary(store_id)
        session_count = int(correlation.get("entry_count") or 0)
        data_confidence = self._data_confidence(session_count)

        visits_by_zone: dict[str, set[str]] = defaultdict(set)
        dwell_by_zone: dict[str, list[int]] = defaultdict(list)

        for event in events:
            if not event.zone_id:
                continue

            if event.event_type == "ZONE_ENTER":
                visits_by_zone[event.zone_id].add(event.visitor_id)

            if event.event_type == "ZONE_DWELL":
                dwell_by_zone[event.zone_id].append(event.dwell_ms)

        if not visits_by_zone:
            return {
                "store_id": store_id,
                "zones": [],
            }

        max_visit_count = max(len(visitor_ids) for visitor_ids in visits_by_zone.values()) or 1

        zones = []

        for zone_id in sorted(visits_by_zone.keys()):
            visit_count = len(visits_by_zone[zone_id])
            dwell_values = dwell_by_zone.get(zone_id, [])

            avg_dwell_ms = (
                round(sum(dwell_values) / len(dwell_values), 2)
                if dwell_values
                else 0.0
            )

            heat_score = round((visit_count / max_visit_count) * 100)

            zones.append(
                {
                    "zone_id": zone_id,
                    "visit_count": visit_count,
                    "avg_dwell_ms": avg_dwell_ms,
                    "heat_score": heat_score,
                    "data_confidence": data_confidence,
                }
            )

        return {
            "store_id": store_id,
            "zones": zones,
        }
