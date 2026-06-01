#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models.pos_transaction import PosTransaction


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [column.strip().lower().replace(" ", "_") for column in df.columns]
    return df


def first_existing(columns: list[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def normalize_pos(input_path: Path, output_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    df = normalize_columns(df)

    columns = list(df.columns)

    order_col = first_existing(columns, ["order_id", "invoice_number", "transaction_id", "bill_no"])
    invoice_col = first_existing(columns, ["invoice_number", "bill_no", "order_id"])
    date_col = first_existing(columns, ["order_date", "date", "bill_date"])
    time_col = first_existing(columns, ["order_time", "time", "bill_time"])
    amount_col = first_existing(columns, ["total_amount", "amount", "net_amount", "basket_value_inr", "nmv"])
    qty_col = first_existing(columns, ["qty", "quantity", "item_count"])
    store_col = first_existing(columns, ["store_id", "store_code"])
    store_name_col = first_existing(columns, ["store_name", "outlet_name"])
    item_col = first_existing(columns, ["product_id", "sku", "ean", "product_name"])

    if not order_col:
        raise ValueError(f"Could not infer transaction/order column. Found columns: {columns}")

    if not amount_col:
        raise ValueError(f"Could not infer amount column. Found columns: {columns}")

    df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0.0)

    if qty_col:
        df[qty_col] = pd.to_numeric(df[qty_col], errors="coerce").fillna(1).astype(int)
    else:
        df["_qty"] = 1
        qty_col = "_qty"

    if date_col and time_col:
        timestamp_series = pd.to_datetime(
            df[date_col].astype(str) + " " + df[time_col].astype(str),
            errors="coerce",
            dayfirst=True,
        )
    elif date_col:
        timestamp_series = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    else:
        timestamp_series = pd.Timestamp("2026-04-10 20:10:00")

    df["_timestamp_ist"] = timestamp_series
    df = df.dropna(subset=["_timestamp_ist"])

    df["_timestamp_utc"] = (
        df["_timestamp_ist"]
        .dt.tz_localize("Asia/Kolkata", ambiguous="NaT", nonexistent="shift_forward")
        .dt.tz_convert("UTC")
    )

    grouped = (
        df.groupby(order_col)
        .agg(
            timestamp_utc=("_timestamp_utc", "min"),
            basket_value_inr=(amount_col, "sum"),
            item_count=(qty_col, "sum"),
        )
        .reset_index()
        .rename(columns={order_col: "transaction_id"})
    )

    if invoice_col:
        invoice_map = df.groupby(order_col)[invoice_col].first().to_dict()
        grouped["invoice_number"] = grouped["transaction_id"].map(invoice_map).fillna(grouped["transaction_id"])
    else:
        grouped["invoice_number"] = grouped["transaction_id"]

    grouped["store_id"] = df[store_col].iloc[0] if store_col else "ST1008"
    grouped["store_name"] = df[store_name_col].iloc[0] if store_name_col else "Brigade_Bangalore"

    if item_col:
        unique_items = df.groupby(order_col)[item_col].nunique().to_dict()
        grouped["unique_items"] = grouped["transaction_id"].map(unique_items).fillna(1).astype(int)
    else:
        grouped["unique_items"] = df.groupby(order_col).size().values

    output_path.parent.mkdir(parents=True, exist_ok=True)
    grouped.to_csv(output_path, index=False)

    return grouped


def seed_transactions(normalized: pd.DataFrame, db: Session) -> tuple[int, int]:
    inserted = 0
    skipped = 0

    for _, row in normalized.iterrows():
        transaction_id = str(row["transaction_id"])

        existing = (
            db.query(PosTransaction)
            .filter(PosTransaction.transaction_id == transaction_id)
            .first()
        )

        if existing:
            skipped += 1
            continue

        timestamp_value = row["timestamp_utc"]
        if hasattr(timestamp_value, "to_pydatetime"):
            timestamp_value = timestamp_value.to_pydatetime()

        db.add(
            PosTransaction(
                transaction_id=transaction_id,
                invoice_number=str(row.get("invoice_number", transaction_id)),
                store_id=str(row.get("store_id", "ST1008")),
                store_name=str(row.get("store_name", "Brigade_Bangalore")),
                timestamp=timestamp_value,
                basket_value_inr=float(row["basket_value_inr"]),
                item_count=int(row["item_count"]),
                unique_items=int(row["unique_items"]),
            )
        )

        inserted += 1

    db.commit()
    return inserted, skipped


def main() -> None:
    input_path = Path("data/raw/pos/Brigade_Bangalore_10_April_26.csv")
    output_path = Path("data/processed/normalized_pos_transactions.csv")

    if not input_path.exists():
        print(f"POS file not found at: {input_path}")
        print("Copy your CSV to this path and rerun this script.")
        return

    init_db()

    normalized = normalize_pos(input_path, output_path)

    db = SessionLocal()

    try:
        inserted, skipped = seed_transactions(normalized, db)
    finally:
        db.close()

    print(f"Normalized POS transactions: {len(normalized)}")
    print(f"Inserted: {inserted}")
    print(f"Skipped duplicates: {skipped}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
