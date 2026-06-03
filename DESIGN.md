# Design Document

## 1. Overview

This project implements an AI-powered Store Intelligence System for the revised Purplle Tech Challenge dataset.

The system converts raw multi-camera CCTV footage into canonical behavioural events and exposes store-level business intelligence through production-style APIs.

The design goal is not only to detect people in video, but to convert imperfect CCTV observations into explainable retail metrics such as:

```text
unique visitors
product-zone engagement
billing queue activity
offline conversion rate
abandonment rate
dwell time
zone heatmap
operational anomalies
```

The implementation is intentionally configuration-driven so that the same pipeline can process multiple stores with different layouts, camera names, and camera roles.

---

## 2. High-level architecture

```text
Raw CCTV footage
        ↓
Store config JSON
        ↓
YOLOv8 person detection
        ↓
ByteTrack tracking
        ↓
Camera-role event generation
        ↓
Canonical event JSONL
        ↓
FastAPI ingestion API
        ↓
SQLite persistence
        ↓
Business metric services
        ↓
Metrics, funnel, heatmap, anomaly, conversion-debug APIs
```

The system separates responsibilities across five layers:

```text
1. Configuration layer
2. Computer-vision pipeline layer
3. Event ingestion layer
4. Business metric layer
5. API and dashboard layer
```

---

## 3. Configuration-driven store design

The revised dataset contains more than one store and each store has its own camera naming, layout, and camera role mapping.

Instead of hardcoding this in Python, store-specific details are externalized into:

```text
configs/stores/store_1.json
configs/stores/store_2.json
```

Each config defines:

```text
store_id
display_name
layout_file
camera_roles
entry_cameras
zone_cameras
billing_cameras
camera-specific zones
staff rules
edge-case policy
business rules
```

This mirrors a production camera registry where each camera is mapped to a store, business role, and layout zone.

### Store 1

```text
store_id: ST1008
entry source: CAM_3
zone cameras: CAM_1, CAM_2
billing camera: CAM_5
POS: available
```

### Store 2

```text
store_id: ST1076
entry source of truth: ENTRY_2
secondary entry camera: ENTRY_1
zone camera: ZONE
billing camera: BILLING
POS: not available in supplied POS CSV
```

---

## 4. Camera-role model

Each camera is assigned one of these roles:

```text
entry
zone
billing
staff
```

The role determines which event types the camera is allowed to emit.

### Entry cameras

Entry cameras emit:

```text
ENTRY
EXIT
REENTRY
```

They are the only cameras allowed to create new customer sessions.

### Zone cameras

Zone cameras emit:

```text
ZONE_ENTER
ZONE_EXIT
ZONE_DWELL
```

They are used for product engagement, dwell time, and heatmap signals.

### Billing cameras

Billing cameras emit:

```text
ZONE_ENTER
ZONE_EXIT
ZONE_DWELL
BILLING_QUEUE_JOIN
```

They are used for queue depth, billing participation, and POS correlation.

### Staff cameras or staff zones

Staff cameras and BOH/service zones mark detections as staff-side movement. Staff detections are excluded from customer metrics.

---

## 5. Canonical event schema

The pipeline writes canonical behavioural events as JSONL.

Each event contains:

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

The design keeps the internal schema stable even if input video files, camera names, or POS formats change.

Example:

```json
{
  "event_id": "uuid",
  "store_id": "ST1008",
  "camera_id": "CAM_5",
  "visitor_id": "VIS_CAM_5_12",
  "event_type": "BILLING_QUEUE_JOIN",
  "timestamp": "2026-04-10T14:40:10Z",
  "zone_id": "ZONE_BILLING_QUEUE",
  "dwell_ms": 0,
  "is_staff": false,
  "confidence": 0.81,
  "metadata": {
    "track_id": 12,
    "queue_depth": 2,
    "queue_depth_method": "rolling_3s_median",
    "camera_role": "billing"
  }
}
```

---

## 6. Detection and tracking design

The computer-vision pipeline uses:

```text
YOLOv8 for person detection
ByteTrack for frame-to-frame person tracking
bottom-center point for zone assignment
polygon-based zone mapping
```

The pipeline samples every N frames to keep processing practical while still producing useful behavioural events.

A person is mapped to a zone using the bottom-center point of the bounding box. This is more stable for retail CCTV than using the box center because the feet position better approximates where the person is standing.

---

## 7. Zone mapping

Each camera has its own zone polygons because the same physical store region appears differently depending on camera angle.

For example:

```text
Store 1 CAM_1:
  ZONE_TOP_WALL
  ZONE_CENTER_MAKEUP_UNIT
  ZONE_FOH

Store 1 CAM_5:
  ZONE_BILLING_QUEUE
  ZONE_CASH_COUNTER
  ZONE_ACCESSORIES

Store 2 BILLING:
  ZONE_BILLING_QUEUE
  ZONE_CASH_COUNTER
  ZONE_BOH
```

The system uses broad business zones rather than brand-level micro-zones. This improves robustness under occlusion, low camera angle, and short clips.

---

## 8. Edge-case handling

The revised challenge expects realistic handling of imperfect footage. The implementation handles the main known challenges as follows.

### 8.1 Group entry

Multiple tracked people entering within a short time window are counted as individual visitors.

The pipeline annotates nearby entry events with:

```text
group_entry
group_size
group_id
```

This prevents the system from collapsing a group into one visitor.

### 8.2 Staff movement

Staff handling is rule-based.

A detection can be marked as staff if:

```text
the camera is marked as staff-side
the person is in a BOH zone
the person is in a service/cash-counter zone
```

Staff detections are excluded from visitor and conversion metrics.

This is explainable and practical for a challenge dataset, while a production version could add uniform detection or staff Re-ID.

### 8.3 Re-entry

The system supports `REENTRY` events and re-entry-aware funnel logic.

Re-entry is not counted as a fresh visitor session in funnel metrics, which avoids inflating footfall when a customer briefly leaves and returns.

### 8.4 Partial occlusion

Low-confidence detections are retained with metadata instead of being silently dropped.

Each event includes:

```text
low_confidence
confidence_band
```

This makes downstream APIs aware of uncertainty.

### 8.5 Billing queue buildup

Billing queue depth is smoothed using a rolling median window.

```text
queue_depth = median(non-staff detections in billing queue ROI over recent frames)
```

This avoids unstable queue depth caused by one noisy frame.

### 8.6 Empty store periods

The APIs return stable zero-state responses when no customer events are available.

This is covered by tests.

### 8.7 Camera overlap

Store 2 has two entry cameras. Without handling, both entry cameras can create duplicate session events for the same real visitor.

The config defines:

```text
entry_source_of_truth: ENTRY_2, ENTRY_1
```

The first camera is treated as the session-counting source of truth. Session events from secondary entry cameras are suppressed when the primary camera has valid session events.

Observed Store 2 result:

```text
raw entry-camera events before suppression: 163 total events
events after suppression: 138 total events
suppressed_entry_overlap_count: 25
```

This reduces visitor denominator inflation.

---

## 9. POS correlation design

The POS dataset does not contain CCTV visitor identity.

Therefore, conversion is estimated through a store-level time-window correlation:

```text
visitor in billing zone
same store_id
POS transaction within configured match window
```

The system does not infer purchases only from CCTV. Conversion requires POS evidence.

This keeps the north-star metric honest.

---

## 10. POS normalization

The revised POS CSV is item-level. It contains 101 raw rows, but those rows represent product-line items rather than 101 separate transactions.

The POS seeding script groups rows by:

```text
store_id + order_date + order_time
```

This normalizes the file into:

```text
24 transaction-level POS records
```

Each normalized POS record includes:

```text
store_id
transaction_id
invoice_number
store_name
timestamp
basket_value_inr
item_count
unique_items
```

This prevents conversion from being inflated by product-line rows.

---

## 11. Business metrics

### 11.1 Unique visitors

Unique visitors are derived from session-counting entry events.

For Store 2, only the configured primary entry camera contributes to the final visitor denominator.

### 11.2 Product-zone visit

A visitor is counted as product-zone engaged when they produce non-staff zone activity.

### 11.3 Billing queue

Billing participation is derived from `BILLING_QUEUE_JOIN` and billing-zone events.

### 11.4 Offline conversion rate

```text
conversion_rate = POS-confirmed converted visitors / unique customer sessions
```

### 11.5 Abandonment rate

For stores with POS data, a billing visitor who cannot be matched to a POS transaction is treated as abandoned.

For stores without POS data, the system avoids inferring abandonment from missing POS and reports this transparently.

---

## 12. API design

The API exposes store-specific endpoints:

```text
POST /events/ingest
GET /health
GET /stores/{store_id}/metrics
GET /stores/{store_id}/funnel
GET /stores/{store_id}/heatmap
GET /stores/{store_id}/anomalies
GET /stores/{store_id}/conversion-debug
```

The `/conversion-debug` endpoint is intentionally included to make metric reasoning auditable.

It reports:

```text
entry_count
product_count
billing_count
converted_count
abandoned_count
transaction_count
matched_transaction_count
unmatched_transaction_count
conversion_source
abandonment_source
```

---

## 13. Health and anomaly design

The health endpoint checks:

```text
database connectivity
latest event timestamp per store
stale-feed warnings
```

For the challenge dataset, `/health` may return:

```text
status: degraded
warning: STALE_FEED
```

This is expected for offline replay because event timestamps are historical.

Anomaly service is designed to support:

```text
stale feed
queue spike
dead zone
conversion baseline unavailable
```

Conversion-drop detection requires historical baselines. Since the supplied dataset is single-day, the system does not fake a seven-day baseline.

---

## 14. Storage design

The system uses SQLite for local challenge execution.

Tables include:

```text
events
pos_transactions
```

SQLite is sufficient for local evaluation and Dockerized demo execution. In production, this would be replaced by PostgreSQL or a streaming warehouse-backed store.

---

## 15. Testing strategy

The test suite covers:

```text
event schema validation
ingestion idempotency
malformed event handling
metrics
funnel
POS correlation
conversion debug
abandonment post-processing
empty-store behaviour
re-entry funnel behaviour
staff exclusion
zone mapping
health response
```

Current validation:

```text
24 tests passed
86% coverage for app + pipeline
```

---

## 16. Production-readiness choices

The system includes:

```text
structured event schema
idempotent event ingestion
request tracing middleware
health endpoint
conversion-debug endpoint
Docker support
test coverage
configuration-driven store setup
raw/generated data ignored by Git
```

The implementation avoids overclaiming perfect computer vision and instead exposes uncertainty using confidence metadata.

---

## 17. Final validation snapshot

### Store 1: ST1008

```text
generated events: 371
accepted events: 371
invalid events: 0
POS transactions loaded: 24
unique visitors: 4
conversion rate: 0.0
abandonment rate: 1.0
```

### Store 2: ST1076

```text
generated events after overlap suppression: 138
accepted events: 138
invalid events: 0
suppressed entry-overlap events: 25
unique visitors: 31
conversion rate: 0.0
abandonment rate: 0.0
```

---

## 18. Limitations

1. Full cross-camera person Re-ID is not implemented.
2. Staff detection is rule-based and does not use a trained uniform classifier.
3. Zone mapping is broad and business-oriented, not brand-level.
4. POS correlation is probabilistic because POS has no customer identity.
5. Conversion-drop anomaly detection requires historical baselines.
6. Offline CCTV replay naturally produces stale-feed health warnings.
7. Camera polygons are manually configured and would need calibration tooling in production.

---

## 19. Future improvements

```text
camera calibration UI for polygon editing
cross-camera Re-ID model
staff uniform classifier
historical baseline store for anomaly detection
Kafka-based event streaming
PostgreSQL instead of SQLite
dashboard with live charts
confidence-weighted metric reporting
automatic store registry validation
```
