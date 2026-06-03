# Metric Definitions

This document defines the business metrics used by the Store Intelligence System.

The system is designed to convert imperfect CCTV observations and POS transactions into explainable offline retail metrics. The most important principle is that customer movement and purchase confirmation are treated separately.

---

## 1. North-star metric

The north-star metric is:

```text
Offline Store Conversion Rate =
POS-confirmed converted visitors / unique customer sessions
```

A customer is counted as converted only when the system can correlate a billing-zone visitor with a POS transaction for the same store within the configured matching window.

The system does not count CCTV billing presence alone as a confirmed purchase.

---

## 2. Unique visitors

### Definition

```text
Unique Visitors = distinct visitor sessions created by ENTRY events
```

Only entry cameras are allowed to create visitor sessions.

### Why this matters

If zone cameras or billing cameras were allowed to create new visitors, the system would inflate footfall. This would make conversion rate artificially low.

### Store 2 overlap handling

Store 2 has two entry cameras:

```text
ENTRY_1
ENTRY_2
```

To avoid double-counting, the system uses a source-of-truth rule:

```text
ENTRY_2 = primary entry source
ENTRY_1 = secondary entry camera
```

Session-counting events from the secondary entry camera are suppressed when primary entry-camera events exist.

Observed Store 2 result:

```text
suppressed_entry_overlap_count = 25
```

---

## 3. Product-zone visit

### Definition

```text
Product-zone visit = visitor has at least one non-staff ZONE_ENTER event
```

The system counts product-zone engagement from zone cameras and business zones such as:

```text
ZONE_FOH
ZONE_TOP_WALL
ZONE_BOTTOM_WALL
ZONE_CENTER_MAKEUP_UNIT
ZONE_LEFT_WALL
ZONE_RIGHT_WALL
ZONE_MAKEUP_GONDOLA
ZONE_MAKEUP_UNIT
```

### Notes

Product-zone visit is not the same as purchase intent. It only indicates that a tracked visitor entered a product or movement zone.

---

## 4. Billing queue participation

### Definition

```text
Billing queue participation =
visitor has BILLING_QUEUE_JOIN or billing-zone activity
```

Billing queue events are generated from billing cameras only.

### Why this matters

Billing queue participation is a strong purchase-intent signal, but it is still not a confirmed purchase. POS evidence is required for conversion.

---

## 5. POS-confirmed converted visitor

### Definition

```text
Converted visitor =
billing-zone visitor matched to a POS transaction for the same store
within the configured POS matching window
```

Matching uses:

```text
store_id
billing-zone timestamp
POS transaction timestamp
configured POS match window
```

The supplied POS data has no customer identity, so exact customer-level matching is not possible.

---

## 6. Conversion rate

### Formula

```text
conversion_rate =
converted_visitor_count / unique_visitor_count
```

If there are no unique visitors, conversion rate returns `0.0`.

### ST1008 observed result

```text
unique visitors = 4
POS transactions loaded = 24
matched POS transactions = 0
conversion rate = 0.0
```

Interpretation:

ST1008 has POS data, but no billing visitor matched a POS transaction within the configured correlation window. The system therefore reports zero conversion instead of falsely assuming purchases.

### ST1076 observed result

```text
unique visitors = 31
POS transactions loaded = 0
conversion rate = 0.0
conversion source = no_pos_transactions_loaded
```

Interpretation:

ST1076 has no POS transactions in the supplied POS CSV. The system reports this transparently rather than inventing conversions.

---

## 7. Abandonment rate

### Definition for stores with POS data

```text
Abandoned visitor =
billing visitor who could not be matched to a POS transaction
```

```text
abandonment_rate =
abandoned_billing_visitors / billing_visitors
```

### ST1008 observed result

```text
billing visitors = 4
converted visitors = 0
abandoned visitors = 4
abandonment rate = 1.0
```

This is expected because POS exists for ST1008, but no billing visitor matched a transaction.

### Stores without POS data

For stores without POS data, the system does not infer abandonment from missing POS.

For example, ST1076 has no POS transactions loaded, so the system avoids treating all billing visitors as abandoned.

---

## 8. Average dwell per zone

### Definition

```text
Average dwell per zone =
average dwell_ms for non-staff ZONE_DWELL / ZONE_EXIT events grouped by zone_id
```

Dwell time estimates how long customers spend in a zone.

### Observed examples

ST1008:

```text
ZONE_FOH: 62850.55 ms
ZONE_BILLING_QUEUE: 30622.5 ms
```

ST1076:

```text
ZONE_BILLING_QUEUE: 30000.0 ms
```

---

## 9. Current queue depth

### Definition

```text
Current queue depth =
latest estimated number of non-staff people in the billing queue zone
```

The pipeline calculates queue depth using a rolling median window to reduce frame-level noise.

### Method

```text
queue_depth = median(non-staff billing-queue detections over recent frames)
```

Observed result:

```text
ST1008 current_queue_depth = 2
ST1076 current_queue_depth = 2
```

---

## 10. Heatmap score

### Definition

```text
Heatmap score =
relative zone activity score based on visit count and dwell intensity
```

A higher heat score indicates stronger activity in that zone compared to other zones in the same store.

### Confidence

Heatmap zones include confidence indicators because CCTV detection may be affected by occlusion, angle, or lighting.

---

## 11. Funnel stages

The funnel has four stages:

```text
ENTRY
PRODUCT_ZONE_VISIT
BILLING_QUEUE
PURCHASE
```

### Stage definitions

```text
ENTRY:
visitor session created from entry camera

PRODUCT_ZONE_VISIT:
visitor reached a product or movement zone

BILLING_QUEUE:
visitor reached billing queue or billing zone

PURCHASE:
visitor matched to POS transaction
```

### ST1008 observed funnel

```text
ENTRY: 4
PRODUCT_ZONE_VISIT: 4
BILLING_QUEUE: 4
PURCHASE: 0
```

### ST1076 observed funnel

```text
ENTRY: 31
PRODUCT_ZONE_VISIT: 10
BILLING_QUEUE: 10
PURCHASE: 0
```

---

## 12. POS normalization metric

The revised POS CSV is item-level.

Raw POS file:

```text
101 rows
```

These rows are product-line items, not 101 purchases.

The system normalizes POS rows into transaction-level records by grouping on:

```text
store_id + order_date + order_time
```

Final normalized POS count:

```text
24 transaction-level records
```

This prevents conversion metrics from being inflated by item-level rows.

---

## 13. Conversion debug fields

The `/stores/{store_id}/conversion-debug` endpoint exposes the reasoning behind conversion and abandonment.

Fields:

```text
entry_count
product_count
billing_count
converted_count
abandoned_count
transaction_count
matched_transaction_count
unmatched_transaction_count
matched_transactions
conversion_source
abandonment_source
```

### Conversion sources

```text
pos_correlation:
POS transactions were loaded and used for matching

no_pos_transactions_loaded:
no POS transactions exist for the requested store
```

### Abandonment sources

```text
unmatched_billing_visitors:
billing visitors were treated as abandoned because POS exists but did not match

explicit_abandon_events:
abandonment is based only on explicit BILLING_QUEUE_ABANDON events
```

---

## 14. Health status

The health endpoint reports:

```text
database connectivity
latest event timestamp per store
stale feed warnings
```

For offline replayed challenge data, the health endpoint can return:

```text
status = degraded
warning = STALE_FEED
```

This is expected because event timestamps come from historical CCTV clips, not a live stream.

Observed clean health stores:

```text
ST1008
ST1076
```

---

## 15. Metric limitations

1. POS correlation is time-window based because POS has no customer identity.
2. Conversion cannot be confirmed without POS.
3. Full cross-camera Re-ID is not implemented.
4. Staff exclusion is rule-based.
5. Brand-level shelf conversion is not supported.
6. Conversion-drop anomaly detection requires historical baselines.
7. Offline dataset replay naturally produces stale-feed warnings.
