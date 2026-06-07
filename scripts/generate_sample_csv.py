#!/usr/bin/env python3
"""Generate a sample transactions CSV for the gRPC pipeline demo."""

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

MERCHANTS = [
    ("Amazon", "retail"),
    ("Starbucks", "food"),
    ("Shell", "fuel"),
    ("Netflix", "entertainment"),
    ("Uber", "transport"),
    ("Walmart", "retail"),
    ("Spotify", "entertainment"),
    ("Apple", "tech"),
    ("Target", "retail"),
    ("McDonald's", "food"),
]

CURRENCIES = ["USD", "EUR", "GBP", "MXN"]


def generate_csv(output_path: Path, rows: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base_date = datetime(2024, 1, 1)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "amount", "currency", "merchant", "timestamp"])

        for index in range(1, rows + 1):
            merchant, _ = random.choice(MERCHANTS)
            amount = round(random.uniform(1.0, 5000.0), 2)
            currency = random.choice(CURRENCIES)
            timestamp = base_date + timedelta(minutes=index * 3)
            writer.writerow([
                f"TXN-{index:06d}",
                amount,
                currency,
                merchant,
                timestamp.isoformat(),
            ])

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Generated {rows} rows -> {output_path} ({size_mb:.2f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rows",
        type=int,
        default=50_000,
        help="Number of transaction rows to generate",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "transactions.csv",
    )
    args = parser.parse_args()
    random.seed(42)
    generate_csv(args.output, args.rows)


if __name__ == "__main__":
    main()
