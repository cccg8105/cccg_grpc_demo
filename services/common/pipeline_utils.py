"""Shared helpers for gRPC pipeline services."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from generated.pipeline.v1 import pipeline_pb2


EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "MXN": 0.058,
}

MERCHANT_CATEGORIES = {
    "Amazon": "retail",
    "Starbucks": "food",
    "Shell": "fuel",
    "Netflix": "entertainment",
    "Uber": "transport",
    "Walmart": "retail",
    "Spotify": "entertainment",
    "Apple": "tech",
    "Target": "retail",
    "McDonald's": "food",
}

HIGH_VALUE_THRESHOLD = float(os.getenv("HIGH_VALUE_THRESHOLD", "1000"))


def transform_record(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Transform a raw transaction row. Returns (result, error)."""
    try:
        amount = float(payload["amount"])
        currency = str(payload["currency"]).upper()
        merchant = str(payload["merchant"])
        rate = EXCHANGE_RATES.get(currency)
        if rate is None:
            return None, f"unsupported currency: {currency}"

        amount_usd = round(amount * rate, 2)
        category = MERCHANT_CATEGORIES.get(merchant, "other")
        result = {
            "id": payload["id"],
            "amount_usd": amount_usd,
            "category": category,
            "merchant": merchant,
            "high_value": amount_usd > HIGH_VALUE_THRESHOLD,
            "original_currency": currency,
            "original_amount": amount,
        }
        return result, None
    except (KeyError, TypeError, ValueError) as exc:
        return None, str(exc)


def preview_record(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=True)


def now_ms() -> int:
    return int(time.time() * 1000)


def csv_row_to_proto(row: dict[str, str]) -> pipeline_pb2.TransactionRecord:
    return pipeline_pb2.TransactionRecord(
        id=row["id"],
        amount=float(row["amount"]),
        currency=row["currency"],
        merchant=row["merchant"],
        timestamp=row["timestamp"],
    )


def proto_record_to_dict(record: pipeline_pb2.TransactionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "amount": record.amount,
        "currency": record.currency,
        "merchant": record.merchant,
        "timestamp": record.timestamp,
    }
