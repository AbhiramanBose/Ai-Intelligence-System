# Metric Definitions

This system is built around one north-star business metric:

Offline Store Conversion Rate = POS-confirmed purchases / unique customer sessions

A purchase is counted only when a POS transaction can be correlated with a visitor who was in the billing zone during the five-minute window before the transaction.

## unique_visitors

`unique_visitors` is the number of unique non-staff visitor sessions observed for the store.

Rules:

* Staff events are excluded using `is_staff=true`.
* `ENTRY` and `REENTRY` are session events.
* `REENTRY` does not inflate the same visitor in the funnel.

## conversion_rate

`conversion_rate = converted_count / unique_visitors`

A converted visitor is POS-confirmed. Billing queue presence alone is not treated as purchase.

Important behavior:

* Zero matched POS transactions means `conversion_rate = 0.0`.
* The value is capped at `1.0` to avoid impossible rates.

## avg_dwell_per_zone

Average dwell time is computed from `ZONE_DWELL` events grouped by `zone_id`.

Rules:

* Staff events are excluded.
* `ZONE_DWELL` is emitted only after 30 seconds of continuous dwell.
* Dwell values are reported in milliseconds.

## current_queue_depth

`current_queue_depth` is taken from the latest non-staff `BILLING_QUEUE_JOIN` event metadata.

## abandonment_rate

`abandonment_rate = abandoned_count / billing_count`

A visitor is considered abandoned when they reached billing but no POS transaction matched within the five-minute correlation window.

The system supports abandonment in two ways:

1. Business metric computation through POS correlation.
2. Explicit `BILLING_QUEUE_ABANDON` events produced by post-processing.

## funnel

The funnel stages are:

ENTRY -> PRODUCT_ZONE_VISIT -> BILLING_QUEUE -> PURCHASE

The funnel is session-based, not raw-event based.

Rules:

* Staff is excluded.
* Re-entry does not double-count the same visitor.
* Purchase is POS-confirmed.
* Counts are capped to prevent impossible funnel growth.

## heat_score

`heat_score` is a normalized 0-100 score based on zone visit frequency.

The hottest zone receives `100`, and other zones are scaled relative to it.

## data_confidence

`data_confidence` communicates whether the sample size is large enough for confident interpretation.

Current rule:

* sessions < 20 -> LOW
* sessions >= 20 -> HIGH

This prevents over-interpreting a short challenge clip as a full-day operational truth.

## conversion-debug endpoint

`GET /stores/{store_id}/conversion-debug` explains the internal conversion calculation.

It returns:

* entry count
* product-zone count
* billing count
* converted count
* abandoned count
* transaction count
* matched transaction count
* unmatched transaction count
* conversion source
* abandonment source

This endpoint exists to make the north-star metric auditable during review and debugging.

