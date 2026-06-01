# PROMPT:
# Generate pytest tests for a diagnostic conversion-debug endpoint that explains POS-confirmed conversion.
# The endpoint should expose counts used to compute conversion_rate and abandonment_rate.
#
# CHANGES MADE:
# Used a unique empty store ID so the test remains deterministic and does not depend on seeded challenge data.

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_conversion_debug_empty_store_response_shape():
    response = client.get("/stores/DEBUG_EMPTY_STORE/conversion-debug")

    assert response.status_code == 200

    payload = response.json()

    assert payload["store_id"] == "DEBUG_EMPTY_STORE"
    assert payload["entry_count"] == 0
    assert payload["product_count"] == 0
    assert payload["billing_count"] == 0
    assert payload["converted_count"] == 0
    assert payload["abandoned_count"] == 0
    assert payload["transaction_count"] == 0
    assert payload["matched_transaction_count"] == 0
    assert payload["unmatched_transaction_count"] == 0
    assert payload["matched_transactions"] == []
    assert "conversion_source" in payload
    assert "abandonment_source" in payload
