import json
import re
import time
import uuid
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


STORE_PATH_PATTERN = re.compile(r"^/stores/([^/]+)")


def _extract_store_id_from_path(path: str) -> str | None:
    match = STORE_PATH_PATTERN.match(path)
    if match:
        return match.group(1)
    return None


def _extract_ingest_metadata(payload: dict[str, Any] | None) -> tuple[str | None, int | None]:
    if not payload:
        return None, None

    events = payload.get("events")

    if not isinstance(events, list):
        return None, None

    event_count = len(events)

    store_ids = {
        event.get("store_id")
        for event in events
        if isinstance(event, dict) and event.get("store_id")
    }

    if len(store_ids) == 1:
        return next(iter(store_ids)), event_count

    if len(store_ids) > 1:
        return "MULTI_STORE", event_count

    return None, event_count


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        endpoint = request.url.path
        store_id = _extract_store_id_from_path(endpoint)
        event_count = None

        if endpoint == "/events/ingest" and request.method.upper() == "POST":
            try:
                raw_body = await request.body()
                if raw_body:
                    payload = json.loads(raw_body.decode("utf-8"))
                    store_id_from_body, event_count_from_body = _extract_ingest_metadata(payload)
                    store_id = store_id_from_body or store_id
                    event_count = event_count_from_body
            except Exception:
                # Logging must never break request processing.
                event_count = None

        response = await call_next(request)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        log_payload = {
            "trace_id": trace_id,
            "store_id": store_id,
            "endpoint": endpoint,
            "method": request.method,
            "latency_ms": latency_ms,
            "event_count": event_count,
            "status_code": response.status_code,
        }

        print(log_payload)

        response.headers["X-Trace-Id"] = trace_id

        return response
