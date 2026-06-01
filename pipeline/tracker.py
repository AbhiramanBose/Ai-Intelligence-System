"""Tracking module. Next iteration will use ByteTrack via supervision."""
from dataclasses import dataclass


@dataclass
class Track:
    track_id: int
    frame_index: int
    bbox: tuple[float, float, float, float]
    confidence: float


def track_detections(detections) -> list[Track]:
    return []
