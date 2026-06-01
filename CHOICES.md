# CHOICES.md

## 1. Detection Model Choice

### Options Considered

```text
YOLOv8
RT-DETR
MediaPipe
Manual frame differencing
```

### Final Choice

```text
YOLOv8n
```

### Reasoning

YOLOv8n was selected because it is fast, easy to run locally, simple to integrate with Python, and sufficient for person detection in retail CCTV footage. It also integrates cleanly with Ultralytics tracking and ByteTrack.

RT-DETR may offer strong detection quality, but it is heavier and less convenient for this challenge timeline. MediaPipe is lightweight, but it is not ideal for multi-person CCTV tracking in retail environments. Manual frame differencing is too brittle for this dataset because of occlusion, lighting, and customer movement.

### Trade-Off

YOLOv8n may miss some heavily occluded people or low-resolution detections, but it provides the best balance of speed, simplicity, and practical reliability.

## 2. Tracking Choice

### Options Considered

```text
Centroid tracking
ByteTrack
DeepSORT
Full person re-identification model
```

### Final Choice

```text
ByteTrack
```

### Reasoning

ByteTrack provides practical multi-person tracking without requiring a separate person re-identification model. It is suitable for short CCTV clips and integrates easily through Ultralytics.

DeepSORT and full Re-ID were considered but not chosen for the initial build because they add implementation complexity and are not necessary to demonstrate the full end-to-end system.

### Trade-Off

The current implementation uses camera-local visitor IDs. This means the same real customer may have different IDs across CAM_1, CAM_2, CAM_3, and CAM_5. To avoid incorrect business metrics, the funnel uses CAM_3 for entry count and caps later stages so the funnel remains logically valid.

## 3. Event Schema Design

### Final Choice

The event schema uses:

```text
event_id
store_id
camera_id
visitor_id
event_type
timestamp
zone_id
dwell_ms
is_staff
confidence
metadata
```

### Reasoning

This schema supports:

```text
Idempotent ingestion through event_id
Store-level querying through store_id
Camera-level debugging through camera_id
Visitor/session-level analysis through visitor_id
Zone analytics through zone_id
Dwell-time analytics through dwell_ms
Staff exclusion through is_staff
Confidence-aware review through confidence
Flexible event-specific details through metadata
```

### Trade-Off

The schema is slightly verbose, but it makes the system easier to debug, replay, and extend.

## 4. API Architecture Choice

### Options Considered

```text
FastAPI + SQLite
FastAPI + PostgreSQL
Node.js + PostgreSQL
Flask + SQLite
```

### Final Choice

```text
FastAPI + SQLite
```

### Reasoning

FastAPI provides strong request validation, simple routing, good testability, and fast development speed. SQLite keeps the project easy to run locally and inside Docker without requiring a separate database setup.

PostgreSQL would be better for production scale, but SQLite is sufficient for the challenge dataset and reduces evaluator setup friction.

### Trade-Off

SQLite is not ideal for high-concurrency production traffic, but it is appropriate for this assignment and keeps the system portable.

## 5. POS Correlation Choice

### Options Considered

```text
Assume billing queue equals purchase
Match POS transaction to billing events using time window
Ignore POS and report only visitor engagement
```

### Final Choice

```text
Match POS transaction to billing events using a five-minute window
```

### Reasoning

The challenge expects conversion to be business meaningful. A customer standing in the billing area should not automatically be considered converted. A purchase should be counted only when there is a matching POS transaction.

The system therefore counts a conversion only if:

```text
billing event timestamp <= POS transaction timestamp <= billing event timestamp + 5 minutes
```

### Dataset Result

For the provided CCTV sample, billing events occur around 14:39 to 14:40 UTC. The nearest POS transactions are about 15 minutes away. Therefore, no transaction matches the five-minute rule, and the final conversion rate is 0.0.

This is intentional and prevents false conversion inflation.

## 6. Zone Granularity Choice

### Options Considered

```text
Brand-level zones
Broad analytics zones
Single whole-store zone
```

### Final Choice

```text
Broad analytics zones
```

### Reasoning

The CCTV layout supports reliable broad-zone mapping. Broad zones include:

```text
ZONE_FOH
ZONE_TOP_WALL_SKINCARE
ZONE_BOTTOM_WALL_MAKEUP
ZONE_CENTER_MAKEUP_UNIT
ZONE_BILLING_QUEUE
ZONE_BILLING
ZONE_PMU
```

Brand-level zones would look more detailed, but the camera angle does not always allow precise customer-to-brand attribution. A customer standing near a shelf may be between multiple brands.

### Trade-Off

Broad zones provide less brand-level detail, but they are more reliable and easier to defend.

## 7. CAM_4 Exclusion Choice

### Decision

CAM_4 is treated as a backroom or staff-side camera and excluded from customer metrics.

### Reasoning

CAM_4 does not show the primary customer journey. Including it would risk polluting customer analytics with staff or operational movement.

## 8. Testing Choice

### Final Approach

The project uses unit tests for:

```text
Schemas
Ingestion
Metrics
Funnel
Health
Zone mapping
POS correlation
```

The YOLO-based CCTV pipeline is treated as an integration/demo script rather than a unit-test target. It is validated by running:

```text
CCTV footage → generated_events.jsonl → replay_events.py → API endpoints
```

### Reasoning

Unit testing YOLO video processing would be slow and brittle. Business logic is unit-tested, while the computer-vision pipeline is validated through generated structured events.

## 9. Known Trade-Off Summary

```text
YOLOv8n over heavier models for speed and simplicity.
ByteTrack over full Re-ID for implementation practicality.
SQLite over PostgreSQL for low setup friction.
Broad zones over brand-level zones for reliability.
POS-based conversion over billing fallback for business correctness.
CAM_4 excluded to avoid contaminating customer metrics.
CCTV pipeline validated as integration flow instead of unit-tested directly.
```
