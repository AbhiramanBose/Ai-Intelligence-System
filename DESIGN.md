# DESIGN.md

## 1. Problem Understanding

The objective is to build an end-to-end offline store intelligence system. The system starts from raw CCTV footage and POS data, then produces business-facing analytics such as visitor count, product-zone engagement, billing queue activity, heatmap, anomalies, and offline conversion rate.

The challenge is not only a computer-vision task. It is a full system design problem involving detection, tracking, event generation, API ingestion, storage, business logic, and clear engineering trade-offs.

## 2. System Overview

```text
CCTV videos
    ↓
Computer vision pipeline
    ↓
Structured event stream
    ↓
FastAPI ingestion service
    ↓
SQLite database
    ↓
Analytics services
    ↓
Metrics, funnel, heatmap, anomalies, health endpoints
```

The system is designed to remain useful even when detection is not perfect. It records confidence values, uses idempotent event ingestion, and separates raw movement events from business metric computation.

## 3. Dataset Context

The project uses the Brigade Bangalore store dataset.

```text
Store ID: ST1008
Store Name: Brigade_Bangalore
Date: 10 April 2026
```

The dataset includes:

```text
CAM_1.mp4
CAM_2.mp4
CAM_3.mp4
CAM_4.mp4
CAM_5.mp4
Brigade_Bangalore_10_April_26.csv
Store layout image and Excel
```

## 4. Camera Role Mapping

### CAM_1

CAM_1 is used for top-wall product-zone analytics.

Visible zones include:

```text
Top-wall skincare shelves
Center product display
Front-of-house movement area
```

Generated events:

```text
ZONE_ENTER
ZONE_EXIT
ZONE_DWELL
```

### CAM_2

CAM_2 is used for bottom-wall makeup/product-zone analytics.

Visible zones include:

```text
Bottom-wall makeup shelves
Center product display
Front-of-house movement area
```

Generated events:

```text
ZONE_ENTER
ZONE_EXIT
ZONE_DWELL
```

### CAM_3

CAM_3 is the primary entry/exit camera.

Generated events:

```text
ENTRY
EXIT
REENTRY, if re-identification is available
```

In the current implementation, ENTRY is detected when a person first appears in the entry zone or transitions from outside corridor to inside entry zone.

### CAM_4

CAM_4 shows a backroom or staff-side area. It is excluded from customer-facing metrics.

### CAM_5

CAM_5 is used for billing and queue analytics.

Generated events:

```text
ZONE_ENTER
ZONE_EXIT
ZONE_DWELL
BILLING_QUEUE_JOIN
```

## 5. Store Zone Model

The system uses broad analytics zones for reliable scoring.

```text
ZONE_ENTRY_EXIT
ZONE_FOH
ZONE_TOP_WALL_SKINCARE
ZONE_BOTTOM_WALL_MAKEUP
ZONE_CENTER_MAKEUP_UNIT
ZONE_BILLING
ZONE_BILLING_QUEUE
ZONE_PMU
ZONE_BACKROOM
```

Broad zones were chosen because the CCTV angles support reliable area-level detection. Brand-level zones are possible, but they are more likely to introduce noisy results because a customer standing near a shelf cannot always be mapped confidently to a single brand.

## 6. Detection and Tracking Pipeline

The detection pipeline is implemented in:

```text
pipeline/run_pipeline.py
```

Pipeline steps:

```text
1. Load CCTV video.
2. Run YOLOv8 person detection.
3. Use ByteTrack tracking through Ultralytics.
4. Compute bottom-center point of each person bounding box.
5. Map the point into camera-specific polygons.
6. Emit structured events.
7. Write events to data/processed/generated_events.jsonl.
```

The bottom-center point is used because it approximates where the person is standing on the floor.

## 7. Event Schema

Each event has:

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

The event schema supports:

```text
Idempotency through event_id
Store-level analytics through store_id
Camera attribution through camera_id
Session-style grouping through visitor_id
Zone analytics through zone_id and dwell_ms
Staff exclusion through is_staff
Confidence-aware debugging through confidence
Flexible additional data through metadata
```

## 8. Event Ingestion

The ingestion endpoint is:

```text
POST /events/ingest
```

It supports:

```text
Batch ingestion
Event validation
Duplicate detection by event_id
Partial success
Structured error reporting
```

Duplicate events are not inserted again. This allows event replay to be safely rerun without inflating metrics.

## 9. Storage

SQLite is used for the starter implementation.

Core tables:

```text
events
pos_transactions
store_zones
anomalies
```

SQLite is sufficient for this challenge because the dataset is small, setup is simple, and the evaluator can run the project without configuring a separate database server.

## 10. Session and Funnel Logic

The funnel has four stages:

```text
ENTRY
PRODUCT_ZONE_VISIT
BILLING_QUEUE
PURCHASE
```

The system treats CAM_3 as the strongest source for entry count. Since current visitor IDs are camera-local, product and billing stages are capped by entry count to keep the funnel logically valid and monotonically decreasing.

Example:

```text
ENTRY >= PRODUCT_ZONE_VISIT >= BILLING_QUEUE >= PURCHASE
```

This avoids impossible outputs such as product visitors being greater than entry visitors.

## 11. POS Normalization

The POS CSV is item-level. The normalizer groups rows into transaction-level records.

Input:

```text
Brigade_Bangalore_10_April_26.csv
```

Output:

```text
data/processed/normalized_pos_transactions.csv
```

Each normalized transaction contains:

```text
transaction_id
invoice_number
store_id
store_name
timestamp_utc
basket_value_inr
item_count
unique_items
```

## 12. POS-Based Conversion

Conversion is calculated using a strict correlation rule:

```text
A visitor is counted as converted only if a billing queue event exists within five minutes before a POS transaction timestamp.
```

This logic is implemented in:

```text
app/services/pos_correlation_service.py
```

The service returns:

```text
entry_count
product_count
billing_count
converted_count
transaction_count
matched_transaction_count
unmatched_transaction_count
conversion_source
```

For the provided demo run, CCTV billing events occur around 14:39 to 14:40 UTC. The nearest POS transactions are approximately 15 minutes away. Therefore, no transaction satisfies the five-minute rule, and the system reports:

```text
conversion_rate = 0.0
PURCHASE count = 0
```

This is intentional. It avoids falsely inflating conversion from billing presence alone.

## 13. Metrics Endpoint

Endpoint:

```text
GET /stores/{store_id}/metrics
```

Returns:

```text
unique_visitors
conversion_rate
average dwell per zone
current queue depth
abandonment_rate
```

Conversion rate is calculated as:

```text
converted_count / unique_visitors
```

The value is capped at 1.0 as a safety guard.

## 14. Heatmap Endpoint

Endpoint:

```text
GET /stores/{store_id}/heatmap
```

The heatmap service returns:

```text
zone_id
visit_count
avg_dwell_ms
heat_score
data_confidence
```

Heat score is normalized from zone visit counts. High-traffic zones receive higher heat scores.

## 15. Anomaly Endpoint

Endpoint:

```text
GET /stores/{store_id}/anomalies
```

Current anomaly types include:

```text
STALE_FEED
BILLING_QUEUE_SPIKE
```

A stale-feed warning is emitted when no recent event has been received within the configured freshness window.

## 16. Health Endpoint

Endpoint:

```text
GET /health
```

Returns:

```text
API status
database status
last event timestamp by store
warnings
```

If the latest event is older than the freshness threshold, the status becomes degraded and a STALE_FEED warning is returned.

## 17. Testing Strategy

The test suite covers:

```text
Event schema validation
Event ingestion
Idempotency
Health endpoint
Metrics endpoint
Funnel endpoint
Zone mapping
POS correlation inside five-minute window
POS non-correlation outside five-minute window
```

Current status:

```text
13 tests passed
Coverage above 80%
```

The CCTV pipeline is treated as an integration/demo pipeline because it runs YOLO and processes videos. It is validated through the generated JSONL event file and API replay flow rather than normal unit tests.

## 18. Known Limitations

1. Cross-camera person re-identification is approximate.
2. Visitor IDs are currently camera-local.
3. The funnel is made session-like by capping later stages using entry count.
4. The CCTV clip is short and does not cover the full business day.
5. The provided POS timestamps do not fall within the five-minute billing window for the demo CCTV clip.
6. Brand-level zone attribution is not used in v1 because broad zones are more reliable for the visible camera angles.

## 19. AI-Assisted Decisions

AI assistance was used for:

```text
Project structure planning
Event schema design
Evaluation-framework interpretation
Test-case planning
POS correlation logic
Documentation drafting
Debugging installation and pytest issues
```

All AI-generated code and tests were reviewed manually, adjusted for the actual dataset, and validated through terminal execution.

## Staff and Re-entry Handling Limitations

The challenge footage includes staff movement, re-entry, group entry, and occlusion. In this version, the system handles these cases with practical approximations rather than claiming perfect visual understanding.

### Staff Handling

The event schema includes `is_staff`, and all customer-facing metrics filter out events where `is_staff=true`. CAM_4 is treated as a backroom or staff-side camera and is excluded from customer metrics. This prevents obvious staff-side movement from contaminating customer analytics.

A production version should improve this with a dedicated staff classifier, for example uniform-color detection, staff badge detection, or a lightweight vision classifier trained on store-specific staff appearances. I did not overclaim this in v1 because the provided footage and timeframe did not support a reliable uniform classifier without additional labelled examples.

### Re-entry Handling

The event catalogue supports `REENTRY`. In this version, CAM_3 is used as the strongest source for entry events, and the funnel logic is capped to prevent cross-camera double counting. However, full cross-camera re-identification is not implemented. The same physical customer may still receive camera-local visitor IDs across different cameras.

A production version should use person re-identification embeddings or trajectory-aware matching across overlapping cameras. This would allow the system to distinguish a true re-entry from a new customer entering from the same direction.

### Group Entry and Occlusion

Group entry is handled through YOLO person detections and ByteTrack track IDs, so multiple people entering together can generate separate tracks. Partial occlusion is handled by retaining confidence scores rather than hiding uncertain detections. Low-confidence events remain visible for review instead of being silently discarded.

These limitations are intentional engineering trade-offs. The current implementation prioritizes a working, explainable end-to-end system over unsupported claims of perfect staff classification or cross-camera re-identification.
