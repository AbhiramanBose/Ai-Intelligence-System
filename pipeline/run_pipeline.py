import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO


LEGACY_STORE_ID = "ST1008"

LEGACY_CAMERA_CONFIGS = {
    "CAM_1": {
        "role": "zone",
        "is_staff_camera": False,
        "zones": {
            "ZONE_TOP_WALL_SKINCARE": [(250, 80), (1800, 80), (1800, 420), (250, 420)],
            "ZONE_CENTER_MAKEUP_UNIT": [(550, 430), (1450, 430), (1450, 850), (550, 850)],
            "ZONE_FOH": [(0, 420), (1920, 420), (1920, 1080), (0, 1080)],
        },
    },
    "CAM_2": {
        "role": "zone",
        "is_staff_camera": False,
        "zones": {
            "ZONE_BOTTOM_WALL_MAKEUP": [(180, 80), (1850, 80), (1850, 430), (180, 430)],
            "ZONE_CENTER_MAKEUP_UNIT": [(450, 430), (1500, 430), (1500, 850), (450, 850)],
            "ZONE_FOH": [(0, 430), (1920, 430), (1920, 1080), (0, 1080)],
        },
    },
    "CAM_3": {
        "role": "entry",
        "is_staff_camera": False,
        "zones": {
            "ZONE_OUTSIDE_CORRIDOR": [(1050, 220), (1920, 180), (1920, 1080), (950, 1080), (900, 700)],
            "ZONE_ENTRY_EXIT": [(120, 0), (1180, 0), (1130, 430), (930, 720), (260, 1080), (120, 1080)],
        },
    },
    "CAM_4": {
        "role": "staff",
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
    x1, _y1, x2, y2 = box
    return int((x1 + x2) / 2), int(y2)


def find_zone(point: tuple[int, int], zones: dict[str, list[tuple[int, int]]]) -> str | None:
    for zone_id, polygon in zones.items():
        if point_in_polygon(point, polygon):
            return zone_id
    return None


def parse_start_time(value: str | None) -> datetime:
    if not value:
        return datetime(2026, 4, 10, 14, 39, 0, tzinfo=timezone.utc)

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def normalize_polygon(raw_polygon: list[list[int]] | list[tuple[int, int]]) -> list[tuple[int, int]]:
    return [(int(point[0]), int(point[1])) for point in raw_polygon]


def normalize_zones(raw_zones: dict[str, Any]) -> dict[str, list[tuple[int, int]]]:
    return {
        zone_id: normalize_polygon(polygon)
        for zone_id, polygon in raw_zones.items()
    }


def load_store_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    required_keys = ["store_id", "camera_roles"]

    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required key '{key}' in {path}")

    return config


def build_camera_specs_from_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    camera_specs: list[dict[str, Any]] = []

    for camera_id, camera_config in config["camera_roles"].items():
        zones = camera_config.get("zones")

        if not zones:
            raise ValueError(f"Camera {camera_id} is missing zones in store config.")

        camera_specs.append(
            {
                "camera_id": camera_id,
                "role": camera_config["role"],
                "file": camera_config["file"],
                "description": camera_config.get("description", ""),
                "is_staff_camera": bool(camera_config.get("is_staff_camera", False)),
                "zones": normalize_zones(zones),
            }
        )

    return camera_specs


def build_camera_specs_from_legacy_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    camera_paths = {
        "CAM_1": args.cam1,
        "CAM_2": args.cam2,
        "CAM_3": args.cam3,
        "CAM_4": args.cam4,
        "CAM_5": args.cam5,
    }

    camera_specs: list[dict[str, Any]] = []

    for camera_id, video_path in camera_paths.items():
        if not video_path:
            continue

        legacy_config = LEGACY_CAMERA_CONFIGS[camera_id]

        camera_specs.append(
            {
                "camera_id": camera_id,
                "role": legacy_config["role"],
                "file": video_path,
                "description": f"Legacy {camera_id} camera",
                "is_staff_camera": bool(legacy_config.get("is_staff_camera", False)),
                "zones": legacy_config["zones"],
            }
        )

    return camera_specs


def is_entry_role(role: str) -> bool:
    return role in {"entry", "entry_exit"}


def is_zone_role(role: str) -> bool:
    return role in {"zone", "top_wall", "bottom_wall"}


def is_billing_role(role: str) -> bool:
    return role == "billing"


def is_staff_role(role: str) -> bool:
    return role in {"staff", "backroom"}


def make_event(
    *,
    store_id: str,
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
        "store_id": store_id,
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


def find_entry_zone(zones: dict[str, list[tuple[int, int]]]) -> str:
    if "ZONE_ENTRY_EXIT" in zones:
        return "ZONE_ENTRY_EXIT"

    for zone_id in zones:
        if "ENTRY" in zone_id:
            return zone_id

    raise ValueError("Entry camera config must contain ZONE_ENTRY_EXIT or another ENTRY zone.")


def find_outside_zones(zones: dict[str, list[tuple[int, int]]]) -> set[str]:
    outside_zones = {
        zone_id
        for zone_id in zones
        if "OUTSIDE" in zone_id or "CORRIDOR" in zone_id
    }

    return outside_zones


def add_confidence_metadata(
    *,
    metadata: dict[str, Any],
    confidence: float,
    edge_case_policy: dict[str, Any],
) -> dict[str, Any]:
    normal_threshold = float(edge_case_policy.get("normal_confidence_threshold", 0.6))
    low_threshold = float(edge_case_policy.get("low_confidence_threshold", 0.35))

    metadata["low_confidence"] = bool(confidence < normal_threshold)
    metadata["confidence_band"] = (
        "very_low" if confidence < low_threshold
        else "low" if confidence < normal_threshold
        else "normal"
    )

    return metadata


def is_staff_detection(
    *,
    role: str,
    camera_config: dict[str, Any],
    current_zone: str,
    staff_rules: dict[str, Any],
) -> bool:
    if bool(camera_config.get("is_staff_camera", False)):
        return True

    if is_staff_role(role):
        return True

    boh_zones = set(staff_rules.get("boh_zones", []))

    if current_zone in boh_zones:
        return True

    return False


def rolling_queue_depth(
    *,
    queue_depth_samples: list[tuple[datetime, int]],
    timestamp: datetime,
    window_seconds: int,
) -> int:
    window_start = timestamp - timedelta(seconds=window_seconds)
    recent_values = [
        depth
        for sample_time, depth in queue_depth_samples
        if sample_time >= window_start
    ]

    if not recent_values:
        return 0

    return int(round(float(np.median(recent_values))))


def process_camera(
    *,
    model: YOLO,
    store_id: str,
    camera_config: dict[str, Any],
    start_time: datetime,
    sample_every_n_frames: int,
    edge_case_policy: dict[str, Any],
    staff_rules: dict[str, Any],
) -> list[dict[str, Any]]:
    camera_id = camera_config["camera_id"]
    role = camera_config["role"]
    video_path = Path(camera_config["file"])
    zones = camera_config["zones"]

    fps = get_video_fps(video_path)

    last_zone_by_track: dict[int, str | None] = {}
    zone_enter_time_by_track: dict[tuple[int, str], datetime] = {}
    last_dwell_emit_by_track_zone: dict[tuple[int, str], datetime] = {}

    entry_last_zone_by_track: dict[int, str | None] = {}
    entry_emitted_tracks: set[int] = set()
    exit_emitted_tracks: set[int] = set()
    reentry_emitted_tracks: set[int] = set()

    queue_depth_samples: list[tuple[datetime, int]] = []
    queue_depth_window_seconds = int(edge_case_policy.get("queue_depth_window_seconds", 3))

    events: list[dict[str, Any]] = []

    entry_zone = find_entry_zone(zones) if is_entry_role(role) else None
    outside_zones = find_outside_zones(zones) if is_entry_role(role) else set()

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

        frame_detections: list[dict[str, Any]] = []

        for box, track_id, confidence in zip(boxes, track_ids, confidences):
            foot_point = bottom_center(box.tolist())
            current_zone = find_zone(foot_point, zones)

            if not current_zone:
                continue

            frame_detections.append(
                {
                    "box": box,
                    "track_id": int(track_id),
                    "confidence": float(confidence),
                    "current_zone": current_zone,
                }
            )

        if is_billing_role(role):
            current_queue_depth_raw = len(
                {
                    detection["track_id"]
                    for detection in frame_detections
                    if detection["current_zone"] == "ZONE_BILLING_QUEUE"
                    and not is_staff_detection(
                        role=role,
                        camera_config=camera_config,
                        current_zone=detection["current_zone"],
                        staff_rules=staff_rules,
                    )
                }
            )
            queue_depth_samples.append((timestamp, current_queue_depth_raw))
            current_queue_depth = rolling_queue_depth(
                queue_depth_samples=queue_depth_samples,
                timestamp=timestamp,
                window_seconds=queue_depth_window_seconds,
            )
        else:
            current_queue_depth = 0

        for detection in frame_detections:
            track_id = detection["track_id"]
            confidence = detection["confidence"]
            current_zone = detection["current_zone"]
            visitor_id = f"VIS_{camera_id}_{track_id}"

            if is_entry_role(role):
                previous_entry_zone = entry_last_zone_by_track.get(track_id)

                entry_by_transition = (
                    previous_entry_zone in outside_zones
                    and current_zone == entry_zone
                )

                entry_by_first_seen = (
                    previous_entry_zone is None
                    and current_zone == entry_zone
                )

                should_emit_entry = entry_by_transition or entry_by_first_seen

                if should_emit_entry:
                    if track_id in exit_emitted_tracks and track_id not in reentry_emitted_tracks:
                        event_type = "REENTRY"
                        reentry_emitted_tracks.add(track_id)
                    elif track_id not in entry_emitted_tracks:
                        event_type = "ENTRY"
                        entry_emitted_tracks.add(track_id)
                    else:
                        entry_last_zone_by_track[track_id] = current_zone
                        last_zone_by_track[track_id] = current_zone
                        continue

                    source = (
                        "entry_zone_transition"
                        if entry_by_transition
                        else "first_seen_entry_zone"
                    )

                    metadata = add_confidence_metadata(
                        metadata={
                            "source": source,
                            "from_zone": previous_entry_zone,
                            "to_zone": current_zone,
                            "track_id": int(track_id),
                            "camera_role": role,
                        },
                        confidence=confidence,
                        edge_case_policy=edge_case_policy,
                    )

                    events.append(
                        make_event(
                            store_id=store_id,
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type=event_type,
                            timestamp=timestamp,
                            zone_id=None,
                            dwell_ms=0,
                            is_staff=False,
                            confidence=confidence,
                            metadata=metadata,
                        )
                    )

                exit_by_transition = (
                    previous_entry_zone == entry_zone
                    and current_zone in outside_zones
                )

                if track_id not in exit_emitted_tracks and exit_by_transition:
                    metadata = add_confidence_metadata(
                        metadata={
                            "source": "entry_zone_transition",
                            "from_zone": previous_entry_zone,
                            "to_zone": current_zone,
                            "track_id": int(track_id),
                            "camera_role": role,
                        },
                        confidence=confidence,
                        edge_case_policy=edge_case_policy,
                    )

                    events.append(
                        make_event(
                            store_id=store_id,
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type="EXIT",
                            timestamp=timestamp,
                            zone_id=None,
                            dwell_ms=0,
                            is_staff=False,
                            confidence=confidence,
                            metadata=metadata,
                        )
                    )
                    exit_emitted_tracks.add(track_id)

                entry_last_zone_by_track[track_id] = current_zone
                last_zone_by_track[track_id] = current_zone
                continue

            is_staff = is_staff_detection(
                role=role,
                camera_config=camera_config,
                current_zone=current_zone,
                staff_rules=staff_rules,
            )

            previous_zone = last_zone_by_track.get(track_id)

            if previous_zone != current_zone:
                if previous_zone:
                    enter_key = (track_id, previous_zone)
                    entered_at = zone_enter_time_by_track.get(enter_key)
                    dwell_ms = 0

                    if entered_at:
                        dwell_ms = int((timestamp - entered_at).total_seconds() * 1000)

                    metadata = add_confidence_metadata(
                        metadata={
                            "track_id": int(track_id),
                            "camera_role": role,
                        },
                        confidence=confidence,
                        edge_case_policy=edge_case_policy,
                    )

                    events.append(
                        make_event(
                            store_id=store_id,
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type="ZONE_EXIT",
                            timestamp=timestamp,
                            zone_id=previous_zone,
                            dwell_ms=dwell_ms,
                            is_staff=is_staff,
                            confidence=confidence,
                            metadata=metadata,
                        )
                    )

                metadata = add_confidence_metadata(
                    metadata={
                        "track_id": int(track_id),
                        "camera_role": role,
                    },
                    confidence=confidence,
                    edge_case_policy=edge_case_policy,
                )

                events.append(
                    make_event(
                        store_id=store_id,
                        camera_id=camera_id,
                        visitor_id=visitor_id,
                        event_type="ZONE_ENTER",
                        timestamp=timestamp,
                        zone_id=current_zone,
                        dwell_ms=0,
                        is_staff=is_staff,
                        confidence=confidence,
                        metadata=metadata,
                    )
                )

                zone_enter_time_by_track[(track_id, current_zone)] = timestamp

                if (
                    is_billing_role(role)
                    and current_zone == "ZONE_BILLING_QUEUE"
                    and not is_staff
                    and current_queue_depth > 0
                ):
                    billing_metadata = add_confidence_metadata(
                        metadata={
                            "track_id": int(track_id),
                            "queue_depth": current_queue_depth,
                            "queue_depth_method": f"rolling_{queue_depth_window_seconds}s_median",
                            "camera_role": role,
                        },
                        confidence=confidence,
                        edge_case_policy=edge_case_policy,
                    )

                    events.append(
                        make_event(
                            store_id=store_id,
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type="BILLING_QUEUE_JOIN",
                            timestamp=timestamp,
                            zone_id=current_zone,
                            dwell_ms=0,
                            is_staff=False,
                            confidence=confidence,
                            metadata=billing_metadata,
                        )
                    )

            if is_zone_role(role) or is_billing_role(role) or is_staff_role(role):
                dwell_key = (track_id, current_zone)
                entered_at = zone_enter_time_by_track.get(dwell_key)

                if entered_at:
                    dwell_seconds = (timestamp - entered_at).total_seconds()
                    last_emit = last_dwell_emit_by_track_zone.get(dwell_key)

                    if dwell_seconds >= 30 and (
                        last_emit is None or (timestamp - last_emit).total_seconds() >= 30
                    ):
                        metadata = add_confidence_metadata(
                            metadata={
                                "track_id": int(track_id),
                                "dwell_threshold_seconds": 30,
                                "camera_role": role,
                            },
                            confidence=confidence,
                            edge_case_policy=edge_case_policy,
                        )

                        events.append(
                            make_event(
                                store_id=store_id,
                                camera_id=camera_id,
                                visitor_id=visitor_id,
                                event_type="ZONE_DWELL",
                                timestamp=timestamp,
                                zone_id=current_zone,
                                dwell_ms=int(dwell_seconds * 1000),
                                is_staff=is_staff,
                                confidence=confidence,
                                metadata=metadata,
                            )
                        )
                        last_dwell_emit_by_track_zone[dwell_key] = timestamp

            last_zone_by_track[track_id] = current_zone

    return events


def parse_event_timestamp(event: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))


def suppress_overlapping_entry_events(
    events: list[dict[str, Any]],
    business_rules: dict[str, Any],
    edge_case_policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    """
    Suppress duplicate session events from secondary entry cameras.

    For stores with multiple entry cameras, the first camera listed in
    business_rules["entry_source_of_truth"] is treated as the session source of truth.

    This is intentionally stricter than timestamp matching because the two entry-camera
    clips may not be perfectly synchronized. It prevents inflated visitor counts and keeps
    the conversion-rate denominator more reliable.
    """
    entry_cameras = business_rules.get("entry_source_of_truth", [])

    if len(entry_cameras) <= 1:
        return events, 0

    primary_entry_camera = entry_cameras[0]
    entry_camera_set = set(entry_cameras)
    suppressible_types = {"ENTRY", "EXIT", "REENTRY"}

    has_primary_session_events = any(
        event["camera_id"] == primary_entry_camera
        and event["event_type"] in suppressible_types
        for event in events
    )

    if not has_primary_session_events:
        return events, 0

    filtered_events: list[dict[str, Any]] = []
    suppressed_count = 0

    for event in events:
        event_type = event["event_type"]
        camera_id = event["camera_id"]

        if event_type not in suppressible_types or camera_id not in entry_camera_set:
            filtered_events.append(event)
            continue

        if camera_id == primary_entry_camera:
            event["metadata"]["entry_camera_priority"] = "primary"
            event["metadata"]["entry_source_of_truth"] = True
            filtered_events.append(event)
            continue

        suppressed_count += 1

    return filtered_events, suppressed_count


def annotate_group_entries(
    events: list[dict[str, Any]],
    edge_case_policy: dict[str, Any],
) -> None:
    group_window_seconds = int(edge_case_policy.get("group_entry_window_seconds", 2))

    entry_events = [
        event
        for event in events
        if event["event_type"] == "ENTRY"
    ]

    entry_events.sort(key=lambda event: (event["store_id"], event["camera_id"], event["timestamp"]))

    used_event_ids: set[str] = set()

    for event in entry_events:
        if event["event_id"] in used_event_ids:
            continue

        event_time = parse_event_timestamp(event)

        group = [
            candidate
            for candidate in entry_events
            if candidate["store_id"] == event["store_id"]
            and candidate["camera_id"] == event["camera_id"]
            and candidate["event_id"] not in used_event_ids
            and abs((parse_event_timestamp(candidate) - event_time).total_seconds()) <= group_window_seconds
        ]

        if len(group) <= 1:
            continue

        group_size = len(group)
        group_id = str(uuid.uuid4())

        for grouped_event in group:
            grouped_event["metadata"]["group_entry"] = True
            grouped_event["metadata"]["group_size"] = group_size
            grouped_event["metadata"]["group_id"] = group_id
            used_event_ids.add(grouped_event["event_id"])


def write_jsonl(events: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CCTV detection pipeline and emit events.")
    parser.add_argument("--store-config", help="Path to multi-store JSON config.")
    parser.add_argument("--store-id", default=LEGACY_STORE_ID)
    parser.add_argument("--cam1", default="data/raw/cctv/ST1008/CAM_1.mp4")
    parser.add_argument("--cam2", default="data/raw/cctv/ST1008/CAM_2.mp4")
    parser.add_argument("--cam3", default="data/raw/cctv/ST1008/CAM_3.mp4")
    parser.add_argument("--cam4", default="data/raw/cctv/ST1008/CAM_4.mp4")
    parser.add_argument("--cam5", default="data/raw/cctv/ST1008/CAM_5.mp4")
    parser.add_argument("--output", default="data/processed/generated_events.jsonl")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--sample-every-n-frames", type=int, default=10)
    parser.add_argument(
        "--start-time",
        default="2026-04-10T14:39:00Z",
        help="UTC start timestamp for frame-derived event timestamps.",
    )
    args = parser.parse_args()

    if args.store_config:
        store_config = load_store_config(Path(args.store_config))
        store_id = store_config["store_id"]
        camera_specs = build_camera_specs_from_config(store_config)
        edge_case_policy = store_config.get("edge_case_policy", {})
        staff_rules = store_config.get("staff_rules", {})
        business_rules = store_config.get("business_rules", {})
    else:
        store_id = args.store_id
        camera_specs = build_camera_specs_from_legacy_args(args)
        edge_case_policy = {
            "group_entry_window_seconds": 2,
            "reentry_match_window_seconds": 600,
            "low_confidence_threshold": 0.35,
            "normal_confidence_threshold": 0.6,
            "queue_depth_window_seconds": 3,
            "overlap_suppression_window_seconds": 3,
        }
        staff_rules = {
            "boh_zones": ["ZONE_BACKROOM"],
            "service_zones": ["ZONE_BILLING"],
            "behind_counter_staff_seconds": 60,
        }
        business_rules = {
            "entry_source_of_truth": ["CAM_3"],
            "zone_source_of_truth": ["CAM_1", "CAM_2"],
            "billing_source_of_truth": ["CAM_5"],
            "pos_match_window_minutes": 5,
        }
    model = YOLO(args.model)
    start_time = parse_start_time(args.start_time)

    all_events: list[dict[str, Any]] = []
    cameras_processed: list[str] = []
    camera_roles: dict[str, str] = {}

    for camera_spec in camera_specs:
        camera_id = camera_spec["camera_id"]
        role = camera_spec["role"]
        video_path = Path(camera_spec["file"])
        camera_roles[camera_id] = role

        if not video_path.exists():
            print(f"Skipping {camera_id}. File not found: {video_path}")
            continue

        print(f"Processing {camera_id} ({role}): {video_path}")

        camera_events = process_camera(
            model=model,
            store_id=store_id,
            camera_config=camera_spec,
            start_time=start_time,
            sample_every_n_frames=args.sample_every_n_frames,
            edge_case_policy=edge_case_policy,
            staff_rules=staff_rules,
        )

        print(f"{camera_id}: generated {len(camera_events)} events")
        all_events.extend(camera_events)
        cameras_processed.append(camera_id)

    all_events.sort(key=lambda event: event["timestamp"])

    all_events, suppressed_entry_overlap_count = suppress_overlapping_entry_events(
        events=all_events,
        business_rules=business_rules,
        edge_case_policy=edge_case_policy,
    )

    all_events.sort(key=lambda event: event["timestamp"])
    annotate_group_entries(all_events, edge_case_policy)

    output_path = Path(args.output)
    write_jsonl(all_events, output_path)

    summary = {
        "store_id": store_id,
        "event_count": len(all_events),
        "output": str(output_path),
        "cameras_processed": cameras_processed,
        "camera_roles": camera_roles,
        "store_config": args.store_config,
        "suppressed_entry_overlap_count": suppressed_entry_overlap_count,
    }

    summary_path = output_path.with_name("detection_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()