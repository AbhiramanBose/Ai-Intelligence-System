"""Helpers for building schema-compliant events."""
from datetime import datetime, timezone
from uuid import uuid4


def build_event(store_id: str, camera_id: str, visitor_id: str, event_type: str, zone_id=None, dwell_ms=0, confidence=0.0, metadata=None):
    return {
        "event_id": str(uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": False,
        "confidence": confidence,
        "metadata": metadata or {},
    }
