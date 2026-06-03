import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal, init_db
from app.models.pos_transaction import PosTransaction


DEFAULT_INPUT_PATHS = [
    Path("data/raw/pos/pos_transactions.csv"),
    Path("data/raw/pos/POS - sample transactionsb1e826f.csv"),
    Path("data/raw/pos/sample_transactions.csv"),
]

DEFAULT_OUTPUT_PATH = Path("data/processed/normalized_pos_transactions.csv")


def parse_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def parse_date_time(order_date: str, order_time: str) -> datetime:
    date_value = order_date.strip()
    time_value = order_time.strip()

    formats = [
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]

    combined = f"{date_value} {time_value}"

    for fmt in formats:
        try:
            parsed = datetime.strptime(combined, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    raise ValueError(f"Could not parse POS timestamp from date/time: {combined}")


def find_input_path() -> Path:
    for path in DEFAULT_INPUT_PATHS:
        if path.exists():
            return path

    raise FileNotFoundError(
        "No POS CSV found. Place the revised POS CSV under data/raw/pos/ "
        "as pos_transactions.csv or update DEFAULT_INPUT_PATHS."
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader]


def normalize_revised_item_level_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Revised POS format is item-level.

    Expected columns:
    order_id, order_date, order_time, store_id, product_id, brand_name, total_amount

    In the provided CSV, order_id is item-row level, not transaction-level.
    Therefore, transaction identity is derived from store_id + order_date + order_time.
    """
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        store_id = row.get("store_id", "").strip()
        order_date = row.get("order_date", "").strip()
        order_time = row.get("order_time", "").strip()

        if not store_id or not order_date or not order_time:
            continue

        grouped[(store_id, order_date, order_time)].append(row)

    normalized: list[dict[str, Any]] = []

    for (store_id, order_date, order_time), transaction_rows in grouped.items():
        timestamp = parse_date_time(order_date, order_time)

        transaction_id = (
            f"{store_id}_{timestamp.strftime('%Y%m%dT%H%M%S')}"
        )

        basket_value = 0.0
        product_ids: set[str] = set()

        for row in transaction_rows:
            product_id = str(row.get("product_id", "")).strip()

            if product_id:
                product_ids.add(product_id)

            raw_amount = (
                row.get("total_amount")
                or row.get("basket_value_inr")
                or row.get("amount")
                or "0"
            )

            try:
                basket_value += float(str(raw_amount).replace(",", "").strip())
            except ValueError:
                continue

        normalized.append(
            {
                "store_id": store_id,
                "transaction_id": transaction_id,
                "invoice_number": transaction_id,
                "store_name": store_id,
                "timestamp_utc": timestamp,
                "basket_value_inr": round(basket_value, 2),
                "item_count": len(transaction_rows),
                "unique_items": len(product_ids),
            }
        )

    normalized.sort(
        key=lambda item: (
            item["store_id"],
            item["timestamp_utc"],
            item["transaction_id"],
        )
    )

    return normalized


def normalize_transaction_level_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Supports older transaction-level CSVs.

    Expected columns may include:
    store_id, transaction_id, timestamp, basket_value_inr
    """
    normalized: list[dict[str, Any]] = []

    for row in rows:
        store_id = row.get("store_id", "").strip()
        transaction_id = (
            row.get("transaction_id")
            or row.get("order_id")
            or ""
        ).strip()

        timestamp_value = (
            row.get("timestamp")
            or row.get("timestamp_utc")
            or row.get("transaction_timestamp")
            or ""
        ).strip()

        if not store_id or not transaction_id or not timestamp_value:
            continue

        basket_value_raw = (
            row.get("basket_value_inr")
            or row.get("total_amount")
            or row.get("amount")
            or "0"
        )

        normalized.append(
            {
                "store_id": store_id,
                "transaction_id": transaction_id,
                "timestamp_utc": parse_datetime(timestamp_value),
                "basket_value_inr": round(float(str(basket_value_raw).replace(",", "").strip()), 2),
            }
        )

    normalized.sort(key=lambda item: (item["store_id"], item["timestamp_utc"], item["transaction_id"]))

    return normalized


def normalize_pos_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    columns = set(rows[0].keys())

    revised_columns = {"order_date", "order_time", "store_id", "total_amount"}

    if revised_columns.issubset(columns):
        return normalize_revised_item_level_rows(rows)

    return normalize_transaction_level_rows(rows)


def write_normalized_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "store_id",
                "transaction_id",
                "invoice_number",
                "store_name",
                "timestamp_utc",
                "basket_value_inr",
                "item_count",
                "unique_items",
            ],
        )
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    "store_id": row["store_id"],
                    "transaction_id": row["transaction_id"],
                    "invoice_number": row.get("invoice_number"),
                    "store_name": row.get("store_name"),
                    "timestamp_utc": row["timestamp_utc"].isoformat().replace("+00:00", "Z"),
                    "basket_value_inr": row["basket_value_inr"],
                    "item_count": row.get("item_count", 0),
                    "unique_items": row.get("unique_items", 0),
                }
            )


def insert_transactions(rows: list[dict[str, Any]]) -> tuple[int, int]:
    init_db()

    db = SessionLocal()
    inserted = 0
    skipped_duplicates = 0

    try:
        for row in rows:
            existing = (
                db.query(PosTransaction)
                .filter(
                    PosTransaction.store_id == row["store_id"],
                    PosTransaction.transaction_id == row["transaction_id"],
                )
                .first()
            )

            if existing:
                skipped_duplicates += 1
                continue

            transaction = PosTransaction(
                store_id=row["store_id"],
                transaction_id=row["transaction_id"],
                invoice_number=row.get("invoice_number"),
                store_name=row.get("store_name"),
                timestamp=row["timestamp_utc"],
                basket_value_inr=row["basket_value_inr"],
                item_count=row.get("item_count", 0),
                unique_items=row.get("unique_items", 0),
            )

            db.add(transaction)
            inserted += 1

        db.commit()
    finally:
        db.close()

    return inserted, skipped_duplicates


def main() -> None:
    input_path = find_input_path()
    rows = read_csv_rows(input_path)
    normalized_rows = normalize_pos_rows(rows)

    write_normalized_csv(normalized_rows, DEFAULT_OUTPUT_PATH)

    inserted, skipped_duplicates = insert_transactions(normalized_rows)

    print(f"Input POS file: {input_path}")
    print(f"Raw POS rows: {len(rows)}")
    print(f"Normalized POS transactions: {len(normalized_rows)}")
    print(f"Inserted: {inserted}")
    print(f"Skipped duplicates: {skipped_duplicates}")
    print(f"Output: {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()