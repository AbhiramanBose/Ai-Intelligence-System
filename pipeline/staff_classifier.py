"""Staff classifier placeholder.

For v1, staff can be marked using camera role, excluded zones, or manual rules.
Later, add uniform/appearance heuristics from CAM 4 and billing camera.
"""

def is_staff_track(camera_id: str, zone_id: str | None = None) -> bool:
    return zone_id == "ZONE_BACKROOM" or camera_id == "CAM_4"
