# Engineering Choices

This document explains the key engineering choices made while building the AI-powered Store Intelligence System for the revised Purplle Tech Challenge dataset.

The challenge is intentionally open-ended, so the goal was to build a system that is not only functional, but also explainable, maintainable, and production-oriented under real-world CCTV constraints.

---

## 1. Chosen architecture

I implemented an event-driven store intelligence architecture:

```text
Raw CCTV footage
        ↓
Computer vision detection and tracking
        ↓
Canonical behavioural events
        ↓
Event ingestion API
        ↓
Database persistence
        ↓
Business metric services
        ↓
Store intelligence APIs and dashboard
```

This architecture separates raw video processing from business metric calculation.

The main reason for this choice is that computer vision output is imperfect and noisy. By converting video observations into structured events first, the system can reason about business metrics independently from the detection layer.

---

## 2. Why configuration-driven multi-store design

The revised dataset contains multiple stores with different camera names, layouts, and camera roles.

Instead of hardcoding store logic inside Python, I moved store-specific details into JSON config files:

```text
configs/stores/store_1.json
configs/stores/store_2.json
```

Each config defines:

```text
store_id
camera video paths
camera roles
camera-specific zone polygons
entry cameras
billing cameras
staff rules
edge-case policy
business rules
```

This makes the pipeline reusable for multiple stores.

For example:

```text
Store 1: ST1008
  CAM_3 is the entry camera
  CAM_5 is the billing camera

Store 2: ST1076
  ENTRY_2 is the primary entry source of truth
  ENTRY_1 is a secondary entry camera
```

This mirrors a production camera registry where each camera is mapped to a store, role, and layout.

---

## 3. Why YOLOv8 and ByteTrack

I chose YOLOv8 for person detection and ByteTrack for person tracking.

### Reasoning

YOLOv8 is practical for this challenge because it is:

```text
easy to run locally
fast enough for short CCTV clips
well-supported
sufficient for person detection
```

ByteTrack is useful because it can assign frame-to-frame track IDs to detected people. This is required for:

```text
zone entry
zone exit
dwell time
billing queue participation
entry events
exit events
```

The system does not claim perfect identity tracking across all cameras. It uses track IDs within camera streams and applies camera-role rules for practical deduplication.

---

## 4. Why role-based camera processing

Different cameras should not create the same business event types.

I used role-based processing:

```text
entry cameras create ENTRY, EXIT, REENTRY
zone cameras create ZONE_ENTER, ZONE_EXIT, ZONE_DWELL
billing cameras create billing queue and queue-depth events
staff cameras or staff zones mark staff-side movement
```

This prevents floor cameras from accidentally creating new visitor sessions and prevents billing cameras from being treated as entry cameras.

This design improves metric quality because each camera has a clear business responsibility.

---

## 5. Why canonical event schema

I created a canonical event schema so all downstream APIs consume consistent event data.

Each event includes:

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

The benefit is that input formats can change without breaking analytics logic.

For example, raw camera names, POS formats, and store layouts can vary, but the API layer still works with the same event schema.

---

## 6. Why bottom-center point for zone mapping

For zone mapping, I used the bottom-center point of the person bounding box.

This is better than using the center of the bounding box because the bottom-center point more closely represents where the person is standing on the store floor.

This improves zone assignment for:

```text
product-zone visits
billing queue detection
dwell time
heatmap calculations
```

---

## 7. Why broad business zones instead of brand-level zones

The store layouts contain many fixtures and brand-specific areas. However, brand-level zones would be fragile for short CCTV clips because of camera angle, occlusion, and detection noise.

I used broad business zones such as:

```text
ZONE_FOH
ZONE_TOP_WALL
ZONE_BOTTOM_WALL
ZONE_CENTER_MAKEUP_UNIT
ZONE_BILLING_QUEUE
ZONE_CASH_COUNTER
ZONE_BOH
```

This is a deliberate trade-off.

Broad zones are more reliable for the challenge and easier to explain. A production system could later add finer zones after camera calibration and brand shelf mapping.

---

## 8. Why POS-confirmed conversion

The north-star business metric is:

```text
Offline Store Conversion Rate =
POS-confirmed converted visitors / unique customer sessions
```

I chose POS-confirmed conversion instead of CCTV-only conversion because CCTV alone cannot prove a purchase.

A customer standing near the billing counter may still leave without buying. Therefore, conversion requires POS evidence.

This prevents inflated conversion rates.

---

## 9. Why POS normalization was needed

The revised POS CSV is item-level, not transaction-level.

It has:

```text
101 raw rows
```

but these rows represent product-line items, not 101 purchases.

I normalized the file into:

```text
24 transaction-level POS records
```

by grouping rows using:

```text
store_id + order_date + order_time
```

This prevents the system from treating every product row as a separate purchase.

---

## 10. Why conversion-debug endpoint exists

I added `/stores/{store_id}/conversion-debug` because conversion is a business-critical metric and should be explainable.

The endpoint exposes:

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

This makes it clear why conversion is zero, whether POS was loaded, and whether transactions matched billing visitors.

For example:

```text
ST1008 has 24 POS transactions loaded, but 0 matched transactions.
ST1076 has no POS transactions loaded, so the system reports no_pos_transactions_loaded.
```

This is better than hiding the reason behind a single conversion number.

---

## 11. Why entry-camera overlap suppression was added

Store 2 has two entry cameras:

```text
ENTRY_1
ENTRY_2
```

Without suppression, both cameras can count the same physical visitor, inflating unique visitors.

I used a source-of-truth rule:

```text
ENTRY_2 is the primary session-counting camera.
ENTRY_1 is treated as secondary for session events.
```

The observed result was:

```text
Store 2 before suppression: 163 events
Store 2 after suppression: 138 events
suppressed_entry_overlap_count: 25
```

This improves the visitor denominator used in conversion and funnel metrics.

---

## 12. Why group entry metadata was added

Group entry is common in retail CCTV. If multiple people enter close together, the system should count them as separate people while still identifying that they entered as a group.

The pipeline adds metadata such as:

```text
group_entry
group_size
group_id
```

This preserves individual visitor counting and gives downstream systems context about group behaviour.

---

## 13. Why staff exclusion is rule-based

The challenge footage can contain staff movement. Staff should not be counted as customers.

I used configurable staff rules:

```text
BOH zones
service zones
staff camera flags
```

This is explainable and easy to configure per store.

A production system could improve this with:

```text
uniform classification
staff Re-ID
staff roster integration
```

For this challenge, rule-based staff exclusion is a reasonable and transparent approach.

---

## 14. Why low-confidence detections are retained

Instead of dropping all low-confidence detections, the system keeps them with confidence metadata:

```text
low_confidence
confidence_band
```

This is important because CCTV footage has occlusion, reflections, and angle issues.

Keeping confidence metadata allows downstream APIs to remain aware of uncertainty.

---

## 15. Why rolling median queue depth

Single-frame queue depth can be noisy because detection can fluctuate frame to frame.

I used a rolling median queue-depth calculation:

```text
queue_depth = median queue count over a recent window
```

This makes queue depth more stable and reduces false spikes.

---

## 16. Why SQLite was chosen

SQLite was chosen for local challenge execution because it is:

```text
simple
portable
easy to reset
sufficient for local Docker demo
```

In production, I would replace SQLite with PostgreSQL or a time-series/event store.

The architecture already separates persistence from services, so this migration would be straightforward.

---

## 17. Why FastAPI was chosen

FastAPI was chosen because it provides:

```text
clear API structure
Pydantic validation
automatic OpenAPI docs
fast local development
easy Docker deployment
```

The API exposes production-style endpoints for health, ingestion, metrics, funnel, heatmap, anomalies, and conversion debugging.

---

## 18. Why the health endpoint can be degraded

The health endpoint reports stale feed warnings when the latest event is older than 10 minutes.

For offline replayed challenge data, this is expected because the event timestamps come from historical CCTV clips.

Therefore:

```text
database: connected
status: degraded
warning: STALE_FEED
```

is acceptable for offline replay.

This behaviour is intentionally transparent and production-like.

---

## 19. Why not implement full cross-camera Re-ID

Full cross-camera Re-ID is complex and would require a dedicated appearance model, careful calibration, and more footage.

For this challenge, I chose a practical approach:

```text
use tracking within each camera
use camera roles to control event generation
use source-of-truth entry camera rules
suppress secondary entry-camera session events
document the limitation clearly
```

This is safer than overclaiming perfect identity resolution.

---

## 20. Why not fake conversion-drop anomaly detection

The challenge mentions conversion-drop anomaly detection against historical baselines.

The supplied dataset is single-day. It does not provide a valid seven-day historical conversion baseline.

Therefore, the system does not fake conversion-drop analytics. It reports baseline unavailability instead.

This is a deliberate decision to keep the analytics honest.

---

## 21. Validation results

Final functional validation:

```text
24 tests passed
86% coverage for app + pipeline
```

Final store replay:

```text
ST1008 accepted events: 371
ST1076 accepted events: 138
duplicate events: 0
invalid events: 0
```

Final POS normalization:

```text
Raw POS rows: 101
Normalized POS transactions: 24
```

Final observed metrics:

```text
ST1008 unique visitors: 4
ST1008 conversion rate: 0.0
ST1008 abandonment rate: 1.0

ST1076 unique visitors: 31
ST1076 conversion rate: 0.0
ST1076 abandonment rate: 0.0
```

---

## 22. Final trade-off summary

| Decision                     | Why                                         |
| ---------------------------- | ------------------------------------------- |
| Config-driven stores         | Supports multiple layouts and camera roles  |
| YOLOv8 + ByteTrack           | Practical local detection and tracking      |
| Canonical events             | Keeps APIs independent of raw video format  |
| POS-confirmed conversion     | Avoids inflated CCTV-only conversion        |
| Broad zones                  | More robust under occlusion and angle noise |
| Entry source of truth        | Prevents Store 2 double-counting            |
| Rule-based staff exclusion   | Explainable and configurable                |
| SQLite                       | Simple local execution                      |
| Conversion-debug API         | Makes business metric reasoning auditable   |
| Baseline-unavailable anomaly | Avoids fake historical analytics            |
