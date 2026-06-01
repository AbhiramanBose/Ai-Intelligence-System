import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO


STORE_ID = "ST1008"

CAMERA_CONFIGS = {
    "CAM_1": {
        "role": "top_wall",
        "is_staff_camera": False,
        "zones": {
            "ZONE_TOP_WALL_SKINCARE": [(250, 80), (1800, 80), (1800, 420), (250, 420)],
            "ZONE_CENTER_MAKEUP_UNIT": [(550, 430), (1450, 430), (1450, 850), (550, 850)],
            "ZONE_FOH": [(0, 420), (1920, 420), (1920, 1080), (0, 1080)],
        },
    },
    "CAM_2": {
        "role": "bottom_wall",
        "is_staff_camera": False,
        "zones": {
            "ZONE_BOTTOM_WALL_MAKEUP": [(180, 80), (1850, 80), (1850, 430), (180, 430)],
            "ZONE_CENTER_MAKEUP_UNIT": [(450, 430), (1500, 430), (1500, 850), (450, 850)],
            "ZONE_FOH": [(0, 430), (1920, 430), (1920, 1080), (0, 1080)],
        },
    },
    "CAM_3": {
        "role": "entry_exit",
        "is_staff_camera": False,
        "zones": {
            "ZONE_OUTSIDE_CORRIDOR": [(1050, 220), (1920, 180), (1920, 1080), (950, 1080), (900, 700)],
            "ZONE_ENTRY_EXIT": [(120, 0), (1180, 0), (1130, 430), (930, 720), (260, 1080), (120, 1080)],
        },
    },
    "CAM_4": {
        "role": "backroom",
        "is_staff_camera": True,
        "zones": {
            "ZONE_BACKROOM": [(0, 0), (1920, 0), (1920, 1080), (0, 1080)],
        },
    },
    "CAM_5": {
        "role": "billing",
        "is_staff_camera": False,
        "zones": {
            "ZONE_BILLING_QUEUE": [(420, 280), (1500, 280), (1500, 920), (420, 920)],
            "ZONE_BILLING": [(1050, 120), (1900, 120), (1900, 700), (1050, 700)],
            "ZONE_PMU": [(0, 200), (520, 200), (520, 900), (0, 900)],
        },
    },
}


def point_in_polygon(point: tuple[int, int], polygon: list[tuple[int, int]]) -> bool:
    contour = np.array(polygon, dtype=np.int32)
    return cv2.pointPolygonTest(contour, point, False) >= 0


def bottom_center(box: list[float]) -> tuple[int, int]:
    x1, y1, x2, y2 = box
    return int((x1 + x2) / 2), int(y2)


def find_zone(point: tuple[int, int], zones: dict[str, list[tuple[int, int]]]) -> str | None:
    for zone_id, polygon in zones.items():
        if point_in_polygon(point, polygon):
            return zone_id
    return None


def make_event(
    *,
    camera_id: str,
    visitor_id: str,
    event_type: str,
    timestamp: datetime,
    zone_id: str | None,
    dwell_ms: int,
    is_staff: bool,
    confidence: float,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": STORE_ID,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": round(float(confidence), 4),
        "metadata": metadata or {},
    }


def get_video_fps(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    cap.release()
    return float(fps)


def estimate_queue_depth(track_ids: np.ndarray) -> int:
    return int(len(set(track_ids.tolist())))


def process_camera(
    *,
    model: YOLO,
    camera_id: str,
    video_path: Path,
    start_time: datetime,
    sample_every_n_frames: int,
) -> list[dict[str, Any]]:
    config = CAMERA_CONFIGS[camera_id]
    zones = config["zones"]
    is_staff_camera = bool(config.get("is_staff_camera", False))
    fps = get_video_fps(video_path)

    last_zone_by_track: dict[int, str | None] = {}
    zone_enter_time_by_track: dict[tuple[int, str], datetime] = {}
    last_dwell_emit_by_track_zone: dict[tuple[int, str], datetime] = {}
    cam3_last_zone_by_track: dict[int, str | None] = {}
    cam3_entry_emitted_tracks: set[int] = set()
    cam3_exit_emitted_tracks: set[int] = set()

    events: list[dict[str, Any]] = []

    results_stream = model.track(
        source=str(video_path),
        stream=True,
        persist=True,
        classes=[0],
        conf=0.20,
        verbose=False,
        tracker="bytetrack.yaml",
    )

    for frame_index, result in enumerate(results_stream):
        if frame_index % sample_every_n_frames != 0:
            continue

        timestamp = start_time + timedelta(seconds=frame_index / fps)

        if result.boxes is None or result.boxes.id is None:
            continue

        boxes = result.boxes.xyxy.cpu().numpy()
        track_ids = result.boxes.id.cpu().numpy().astype(int)
        confidences = result.boxes.conf.cpu().numpy()

        for box, track_id, confidence in zip(boxes, track_ids, confidences):
            visitor_id = f"VIS_{camera_id}_{track_id}"
            foot_point = bottom_center(box.tolist())
            current_zone = find_zone(foot_point, zones)

            if not current_zone:
                continue

            previous_zone = last_zone_by_track.get(track_id)

            if config["role"] == "entry_exit":
                previous_cam3_zone = cam3_last_zone_by_track.get(track_id)

                entry_by_transition = (
                    previous_cam3_zone == "ZONE_OUTSIDE_CORRIDOR"
                    and current_zone == "ZONE_ENTRY_EXIT"
                )

                entry_by_first_seen = (
                    previous_cam3_zone is None
                    and current_zone == "ZONE_ENTRY_EXIT"
                )

                if (
                    track_id not in cam3_entry_emitted_tracks
                    and (entry_by_transition or entry_by_first_seen)
                ):
                    source = (
                        "cam3_zone_transition"
                        if entry_by_transition
                        else "cam3_first_seen_entry_zone"
                    )

                    events.append(
                        make_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type="ENTRY",
                            timestamp=timestamp,
                            zone_id=None,
                            dwell_ms=0,
                            is_staff=False,
                            confidence=confidence,
                            metadata={
                                "source": source,
                                "from_zone": previous_cam3_zone,
                                "to_zone": current_zone,
                                "track_id": int(track_id),
                            },
                        )
                    )
                    cam3_entry_emitted_tracks.add(track_id)

                exit_by_transition = (
                    previous_cam3_zone == "ZONE_ENTRY_EXIT"
                    and current_zone == "ZONE_OUTSIDE_CORRIDOR"
                )

                if track_id not in cam3_exit_emitted_tracks and exit_by_transition:
                    events.append(
                        make_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type="EXIT",
                            timestamp=timestamp,
                            zone_id=None,
                            dwell_ms=0,
                            is_staff=False,
                            confidence=confidence,
                            metadata={
                                "source": "cam3_zone_transition",
                                "from_zone": previous_cam3_zone,
                                "to_zone": current_zone,
                                "track_id": int(track_id),
                            },
                        )
                    )
                    cam3_exit_emitted_tracks.add(track_id)

                cam3_last_zone_by_track[track_id] = current_zone
                last_zone_by_track[track_id] = current_zone
                continue
            if previous_zone != current_zone:
                if previous_zone:
                    enter_key = (track_id, previous_zone)
                    entered_at = zone_enter_time_by_track.get(enter_key)
                    dwell_ms = 0

                    if entered_at:
                        dwell_ms = int((timestamp - entered_at).total_seconds() * 1000)

                    events.append(
                        make_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type="ZONE_EXIT",
                            timestamp=timestamp,
                            zone_id=previous_zone,
                            dwell_ms=dwell_ms,
                            is_staff=is_staff_camera,
                            confidence=confidence,
                            metadata={"track_id": int(track_id)},
                        )
                    )

                events.append(
                    make_event(
                        camera_id=camera_id,
                        visitor_id=visitor_id,
                        event_type="ZONE_ENTER",
                        timestamp=timestamp,
                        zone_id=current_zone,
                        dwell_ms=0,
                        is_staff=is_staff_camera,
                        confidence=confidence,
                        metadata={"track_id": int(track_id)},
                    )
                )

                zone_enter_time_by_track[(track_id, current_zone)] = timestamp

                if current_zone == "ZONE_BILLING_QUEUE":
                    events.append(
                        make_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type="BILLING_QUEUE_JOIN",
                            timestamp=timestamp,
                            zone_id=current_zone,
                            dwell_ms=0,
                            is_staff=False,
                            confidence=confidence,
                            metadata={
                                "track_id": int(track_id),
                                "queue_depth": estimate_queue_depth(track_ids),
                            },
                        )
                    )

            dwell_key = (track_id, current_zone)
            entered_at = zone_enter_time_by_track.get(dwell_key)

            if entered_at:
                dwell_seconds = (timestamp - entered_at).total_seconds()
                last_emit = last_dwell_emit_by_track_zone.get(dwell_key)

                if dwell_seconds >= 30 and (
                    last_emit is None or (timestamp - last_emit).total_seconds() >= 30
                ):
                    events.append(
                        make_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type="ZONE_DWELL",
                            timestamp=timestamp,
                            zone_id=current_zone,
                            dwell_ms=int(dwell_seconds * 1000),
                            is_staff=is_staff_camera,
                            confidence=confidence,
                            metadata={
                                "track_id": int(track_id),
                                "dwell_threshold_seconds": 30,
                            },
                        )
                    )
                    last_dwell_emit_by_track_zone[dwell_key] = timestamp

            last_zone_by_track[track_id] = current_zone

    return events


def write_jsonl(events: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CCTV detection pipeline and emit events.")
    parser.add_argument("--store-id", default=STORE_ID)
    parser.add_argument("--cam1", default="data/raw/cctv/ST1008/CAM_1.mp4")
    parser.add_argument("--cam2", default="data/raw/cctv/ST1008/CAM_2.mp4")
    parser.add_argument("--cam3", default="data/raw/cctv/ST1008/CAM_3.mp4")
    parser.add_argument("--cam4", default="data/raw/cctv/ST1008/CAM_4.mp4")
    parser.add_argument("--cam5", default="data/raw/cctv/ST1008/CAM_5.mp4")
    parser.add_argument("--output", default="data/processed/generated_events.jsonl")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--sample-every-n-frames", type=int, default=10)
    args = parser.parse_args()

    if args.store_id != STORE_ID:
        raise ValueError(f"This pipeline is configured for {STORE_ID}, got {args.store_id}")

    model = YOLO(args.model)

    start_time = datetime(2026, 4, 10, 14, 39, 0, tzinfo=timezone.utc)

    camera_paths = {
        "CAM_1": Path(args.cam1),
        "CAM_2": Path(args.cam2),
        "CAM_3": Path(args.cam3),
        "CAM_4": Path(args.cam4),
        "CAM_5": Path(args.cam5),
    }

    all_events: list[dict[str, Any]] = []

    for camera_id, video_path in camera_paths.items():
        if not video_path.exists():
            print(f"Skipping {camera_id}. File not found: {video_path}")
            continue

        print(f"Processing {camera_id}: {video_path}")

        camera_events = process_camera(
            model=model,
            camera_id=camera_id,
            video_path=video_path,
            start_time=start_time,
            sample_every_n_frames=args.sample_every_n_frames,
        )

        print(f"{camera_id}: generated {len(camera_events)} events")
        all_events.extend(camera_events)

    all_events.sort(key=lambda event: event["timestamp"])

    output_path = Path(args.output)
    write_jsonl(all_events, output_path)

    summary = {
        "store_id": STORE_ID,
        "event_count": len(all_events),
        "output": str(output_path),
        "cameras_processed": list(camera_paths.keys()),
    }

    summary_path = Path("data/processed/detection_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()