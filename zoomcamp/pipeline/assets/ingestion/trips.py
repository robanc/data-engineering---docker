"""
@bruin
name: ingestion.trips
type: python
image: python:3.11
connection: bigquery-defaultss

materialization:
  type: table
  strategy: append

columns:
  - name: taxi_type
    type: string
    description: "Taxi type (yellow or green)"
  - name: extracted_at
    type: timestamp
    description: "Timestamp when data was extracted"
@bruin
"""

import json
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional, List, Dict

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/"
DEFAULT_START = "2024-01-01"
DEFAULT_END = "2024-02-01"

# Safety rail (homework year)
MAX_YEAR = 2024

# ✅ IMPORTANT: keep ingestion skinny to avoid OOM.
# Keep only what staging.trips uses (plus join key payment_type).
# Yellow uses tpep_*, green uses lpep_*.
KEEP_COLS_COMMON = {"PULocationID", "DOLocationID", "fare_amount", "payment_type"}
KEEP_COLS_YELLOW = KEEP_COLS_COMMON | {"tpep_pickup_datetime", "tpep_dropoff_datetime"}
KEEP_COLS_GREEN = KEEP_COLS_COMMON | {"lpep_pickup_datetime", "lpep_dropoff_datetime"}


def _first_day_of_month(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _parse_date_env(var_name: str, default_value: str) -> datetime:
    value = os.environ.get(var_name, default_value)
    return datetime.strptime(value, "%Y-%m-%d")


def _get_taxi_types() -> List[str]:
    """
    Default to ['yellow'] to avoid OOM in cloud.
    Set BRUIN_VARS='{"taxi_types":["yellow","green"]}' to run both.
    """
    try:
        vars_json = json.loads(os.environ.get("BRUIN_VARS", "{}"))
    except Exception:
        vars_json = {}

    taxi_types = vars_json.get("taxi_types", ["yellow"])
    if isinstance(taxi_types, str):
        taxi_types = [taxi_types]

    taxi_types = [str(t).strip() for t in taxi_types if str(t).strip()]
    return taxi_types or ["yellow"]


def _month_starts_between(start_date: datetime, end_date: datetime) -> List[datetime]:
    months: List[datetime] = []
    current = _first_day_of_month(start_date)
    end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

    while current <= end:
        months.append(current)
        current = current + relativedelta(months=1)
    return months


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "taxi_type": pd.Series(dtype="string"),
            "extracted_at": pd.Series(dtype="datetime64[ns]"),
        }
    )


def _download_parquet(url: str, filename: str) -> Optional[pd.DataFrame]:
    try:
        resp = requests.get(url, timeout=90)
        resp.raise_for_status()
        return pd.read_parquet(BytesIO(resp.content))
    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status in (403, 404):
            print(f"Unavailable ({status}) for {filename} (skipping)")
            return None
        raise


def _select_columns(df: pd.DataFrame, taxi_type: str) -> pd.DataFrame:
    keep = KEEP_COLS_YELLOW if taxi_type == "yellow" else KEEP_COLS_GREEN
    existing = [c for c in df.columns if c in keep]
    return df[existing].copy()


def _strip_timezones_inplace(df: pd.DataFrame) -> None:
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.tz_localize(None)


def materialize() -> pd.DataFrame:
    start_date = _parse_date_env("BRUIN_START_DATE", DEFAULT_START)
    end_date = _parse_date_env("BRUIN_END_DATE", DEFAULT_END)

    if end_date < start_date:
        raise ValueError("BRUIN_END_DATE is before BRUIN_START_DATE")

    taxi_types = _get_taxi_types()
    months = _month_starts_between(start_date, end_date)

    extracted_at = datetime.now(timezone.utc).replace(tzinfo=None)

    all_parts: List[pd.DataFrame] = []
    total_rows = 0

    print(f"Interval: {start_date:%Y-%m-%d} -> {end_date:%Y-%m-%d}")
    print(f"Taxi types: {taxi_types}")

    for month_date in months:
        year = month_date.year
        month = month_date.month

        if MAX_YEAR is not None and year > MAX_YEAR:
            print(f"Skipping {year}-{month:02d} (year exceeds MAX_YEAR={MAX_YEAR})")
            continue

        for taxi_type in taxi_types:
            filename = f"{taxi_type}_tripdata_{year}-{month:02d}.parquet"
            url = f"{BASE_URL}{filename}"

            df = _download_parquet(url, filename)
            if df is None:
                continue

            # ✅ Reduce memory: keep only required columns
            df = _select_columns(df, taxi_type)

            df["taxi_type"] = taxi_type
            df["extracted_at"] = extracted_at

            _strip_timezones_inplace(df)

            all_parts.append(df)
            total_rows += len(df)

            print(f"Downloaded {filename} ({len(df)} rows, cols={len(df.columns)})")

    if not all_parts:
        print("No data downloaded. Returning empty DataFrame with schema.")
        return _empty_result()

    combined = pd.concat(all_parts, ignore_index=True)
    print(f"Total rows combined: {len(combined)}")
    return combined