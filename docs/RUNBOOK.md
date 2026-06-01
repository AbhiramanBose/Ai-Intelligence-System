# Store Intelligence Runbook

This runbook explains how to operate, verify, and debug the Store Intelligence system.

## Start the API

Using Docker:

```bash
docker compose up --build
```

Using local Python:

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Health check

```bash
curl http://localhost:8000/health
```

Expected response shape:

```json
{
  "status": "healthy or degraded",
  "database": "connected",
  "last_event_timestamp_by_store": {},
  "warnings": []
}
```

## STALE_FEED warning

`STALE_FEED` appears when the latest event timestamp for a store is older than 10 minutes.

For this challenge dataset, this warning is expected after replay because the CCTV-derived timestamps are historical.

This is not an API failure. It means the health endpoint is behaving like an on-call diagnostic endpoint.

## Reset local database

Stop the API first, then run:

```bash
rm -f storage/store_intelligence.db
python scripts/seed_pos_transactions.py
```

Then restart the API.

Do not delete the SQLite DB while the API process is running, because the running process may keep an open handle to the old file.

## Generate events from CCTV

```bash
python pipeline/run_pipeline.py \
  --store-id ST1008 \
  --cam1 data/raw/cctv/ST1008/CAM_1.mp4 \
  --cam2 data/raw/cctv/ST1008/CAM_2.mp4 \
  --cam3 data/raw/cctv/ST1008/CAM_3.mp4 \
  --cam4 data/raw/cctv/ST1008/CAM_4.mp4 \
  --cam5 data/raw/cctv/ST1008/CAM_5.mp4 \
  --output data/processed/generated_events.jsonl
```

## Add explicit billing abandonment events

```bash
python scripts/postprocess_abandonment_events.py \
  --events data/processed/generated_events.jsonl \
  --pos data/processed/normalized_pos_transactions.csv \
  --output data/processed/generated_events_with_pos.jsonl
```

This appends `BILLING_QUEUE_ABANDON` events for billing visitors who do not match a POS transaction within the five-minute correlation window.

## Replay events into the API

```bash
python scripts/replay_events.py --file data/processed/generated_events_with_pos.jsonl
```

Expected clean run:

```json
{
  "accepted_count": 346,
  "duplicate_count": 0,
  "invalid_count": 0
}
```

If replaying the same file again, duplicates are expected:

```json
{
  "accepted_count": 0,
  "duplicate_count": 346,
  "invalid_count": 0
}
```

That confirms idempotency.

## Verify business metrics

```bash
curl http://localhost:8000/stores/ST1008/metrics
curl http://localhost:8000/stores/ST1008/funnel
curl http://localhost:8000/stores/ST1008/heatmap
curl http://localhost:8000/stores/ST1008/anomalies
curl http://localhost:8000/stores/ST1008/conversion-debug
```

Expected interpretation for the provided ST1008 run:

* `conversion_rate` is `0.0` because no POS transaction matched the billing events within five minutes.
* `abandonment_rate` is `1.0` because billing visitors did not convert.
* heatmap confidence is `LOW` because the observed session count is below 20.
* `STALE_FEED` is expected because the replayed CCTV timestamp is historical.

## Live terminal dashboard

Start API, then run:

```bash
python dashboard/terminal_dashboard.py --store-id ST1008 --refresh-seconds 2
```

In another terminal, replay events slowly:

```bash
python scripts/replay_events_realtime.py \
  --file data/processed/generated_events_with_pos.jsonl \
  --batch-size 10 \
  --delay-seconds 1.5
```

The dashboard polls metrics, funnel, heatmap, anomalies, and health while events are flowing into the API.

## Common issues

### Port 8000 already in use

```bash
lsof -i :8000
kill -9 <PID>
```

If Docker is using the port:

```bash
docker compose down
```

### Database unavailable

Restart the API after recreating the DB:

```bash
rm -f storage/store_intelligence.db
python scripts/seed_pos_transactions.py
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Duplicate events

Duplicates are expected when replaying the same event file more than once. The ingest endpoint is idempotent by `event_id`.

### Conversion rate remains zero

This is expected when POS timestamps do not match billing events in the five-minute correlation window.

Use:

```bash
curl http://localhost:8000/stores/ST1008/conversion-debug
```

to inspect the exact counts.

