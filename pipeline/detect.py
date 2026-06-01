"""YOLOv8 person detection module. To be completed in the next iteration."""
from dataclasses import dataclass


@dataclass
class Detection:
    frame_index: int
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


def detect_people(video_path: str, confidence_threshold: float = 0.20) -> list[Detection]:
    # Next step: use ultralytics.YOLO("yolov8n.pt") and keep class_id == 0 person detections.
    return []
