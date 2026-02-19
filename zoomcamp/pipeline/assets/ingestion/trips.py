"""@bruin
name: ingestion.trips
type: python
image: python:3.11
connection: bigquery-defaultss

materialization:
  type: table
  strategy: append

script: zoomcamp/pipeline/assets/ingestion/trips.py

columns:
  - name: taxi_type
    type: string
  - name: extracted_at
    type: timestamp
@bruin"""

import json
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import List, Optional

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/"
DEFAULT_START = "2024-01-01"
DEFAULT_END = "2024-01-31"

# Optional safety rail
MAX_YEAR = 2024

# Only pull what staging needs (reduces memory a LOT)
YELLOW_COLS = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "fare_amount",
    "payment_type",
]
GREEN_COLS = [
    "lpep_pickup_datetime",
    "lpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "fare_amount",
    "payment_type",
]


def _first_day_of_month_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _parse_date_env(var_name: str, default_value: str) -> datetime:
    value = os.environ.get(var_name, default_value)
    return datetime.strptime(value, "%Y-%m-%d")


def _get_taxi_types() -> List[str]:
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
    current = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    while current <= end:
        months.append(current)
        current = current + relativedelta(months=1)
    return months


def _strip_timezones_inplace(df: pd.DataFrame) -> None:
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.tz_localize(None)


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "taxi_type": pd.Series(dtype="string"),
            "extracted_at": pd.Series(dtype="datetime64[ns]"),
        }
    )


def _download_parquet_to_df(url: str, filename: str, columns: List[str]) -> Optional[pd.DataFrame]:
    try:
        resp = requests.get(url, timeout=90)
        resp.raise_for_status()
        return pd.read_parquet(BytesIO(resp.content), columns=columns)
    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status in (403, 404):
            print(f"Unavailable ({status}) for {filename} (skipping)")
            return None
        raise


def materialize() -> pd.DataFrame:
    start_date = _parse_date_env("BRUIN_START_DATE", DEFAULT_START)
    end_date = _parse_date_env("BRUIN_END_DATE", DEFAULT_END)

    if end_date < start_date:
        raise ValueError(
            f"BRUIN_END_DATE {end_date:%Y-%m-%d} is before BRUIN_START_DATE {start_date:%Y-%m-%d}"
        )

    taxi_types = _get_taxi_types()
    months_to_process = _month_starts_between(start_date, end_date)

    extracted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    this_month_utc = _first_day_of_month_utc(datetime.now(timezone.utc))

    all_dataframes: List[pd.DataFrame] = []

    print(f"Interval: {start_date:%Y-%m-%d} -> {end_date:%Y-%m-%d}")
    print(f"Taxi types: {taxi_types}")

    for month_date in months_to_process:
        month_start_utc = _first_day_of_month_utc(month_date.replace(tzinfo=timezone.utc))
        if month_start_utc >= this_month_utc:
            print(f"Skipping {month_date:%Y-%m} (current/future month)")
            continue

        year = month_date.year
        month = month_date.month

        if MAX_YEAR is not None and year > MAX_YEAR:
            print(f"Skipping {year}-{month:02d} (year exceeds MAX_YEAR={MAX_YEAR})")
            continue

        for taxi_type in taxi_types:
            filename = f"{taxi_type}_tripdata_{year}-{month:02d}.parquet"
            url = f"{BASE_URL}{filename}"

            cols = YELLOW_COLS if taxi_type == "yellow" else GREEN_COLS
            df = _download_parquet_to_df(url, filename, cols)
            if df is None:
                continue

            df["taxi_type"] = taxi_type
            df["extracted_at"] = extracted_at

            _strip_timezones_inplace(df)
            all_dataframes.append(df)

            print(f"Downloaded {filename} ({len(df)} rows, cols={len(df.columns)})")

    if not all_dataframes:
        print("No data downloaded for the requested interval. Returning empty DataFrame with schema.")
        return _empty_result()

    combined_df = pd.concat(all_dataframes, ignore_index=True)
    print(f"Total rows combined: {len(combined_df)}")
    return combined_df