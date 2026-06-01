"""Lightweight re-entry placeholder. Full Re-ID can be added after baseline is stable."""

def assign_visitor_id(store_id: str, camera_id: str, track_id: int) -> str:
    return f"VIS_{store_id}_{camera_id}_{track_id}"
