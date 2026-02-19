import json
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional  # ✅ FIX: avoid Python 3.10+ union syntax that can break asset discovery

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta


BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/"
DEFAULT_START = "2024-01-01"
DEFAULT_END = "2024-01-31"

# Optional safety rail for the homework (prevents accidental 2026 runs)
# Set to None to disable.
MAX_YEAR = 2024


def _first_day_of_month_utc(dt: datetime) -> datetime:
    """Return the first day of the month in UTC, at 00:00:00."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _parse_date_env(var_name: str, default_value: str) -> datetime:
    """Parse BRUIN_START_DATE / BRUIN_END_DATE (YYYY-MM-DD). Returns naive datetime."""
    value = os.environ.get(var_name, default_value)
    return datetime.strptime(value, "%Y-%m-%d")


def _get_taxi_types() -> list[str]:
    """Read taxi_types from BRUIN_VARS; default to ['yellow'] if not set."""
    try:
        vars_json = json.loads(os.environ.get("BRUIN_VARS", "{}"))
    except Exception:
        vars_json = {}

    taxi_types = vars_json.get("taxi_types", ["yellow"])
    if isinstance(taxi_types, str):
        taxi_types = [taxi_types]

    taxi_types = [str(t).strip() for t in taxi_types if str(t).strip()]
    return taxi_types or ["yellow"]


def _month_starts_between(start_date: datetime, end_date: datetime) -> list[datetime]:
    """Generate month-start datetimes (naive) from start_date to end_date (inclusive)."""
    months: list[datetime] = []
    current = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

    while current <= end:
        months.append(current)
        current = current + relativedelta(months=1)
    return months


def _strip_timezones_inplace(df: pd.DataFrame) -> None:
    """Make all datetime-like columns timezone-naive to avoid pyarrow timezone issues."""
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.tz_localize(None)
            except Exception:
                pass

    for col in df.select_dtypes(include=["object"]).columns:
        col_l = col.lower()
        if col.endswith("datetime") or "datetime" in col_l or col.endswith("_at") or col_l.endswith("_ts"):
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if pd.api.types.is_datetime64_any_dtype(parsed):
                    df[col] = parsed.dt.tz_localize(None)
            except Exception:
                pass


def _empty_result() -> pd.DataFrame:
    """
    Return an empty DataFrame WITH the declared schema columns.
    This avoids failures where the loader expects known columns even when there are 0 rows.
    """
    return pd.DataFrame(
        {
            "taxi_type": pd.Series(dtype="string"),
            "extracted_at": pd.Series(dtype="datetime64[ns]"),
        }
    )


def _download_parquet_to_df(url: str, filename: str) -> Optional[pd.DataFrame]:
    """
    Download a parquet file. Returns a DataFrame if successful, None if unavailable (403/404).
    Raises for other errors.
    """
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return pd.read_parquet(BytesIO(resp.content))
    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status in (403, 404):
            print(f"Unavailable ({status}) for {filename} (skipping)")
            return None
        print(f"HTTP error for {filename}: {e}")
        raise
    except Exception as e:
        print(f"Error downloading/reading {filename}: {e}")
        raise


def materialize() -> pd.DataFrame:
    """
    Fetch NYC taxi trip data from TLC public endpoint.

    Uses taxi_types (from BRUIN_VARS) and date range from BRUIN_START_DATE / BRUIN_END_DATE
    to download parquet files and combine them into a single DataFrame.

    Fixes included:
      - Default dates set to 2024 (common homework range)
      - Safety guard for accidental future years (MAX_YEAR)
      - Skips current/future months
      - Skips missing/unavailable months (HTTP 403/404)
      - Returns an EMPTY DataFrame with schema (taxi_type, extracted_at) instead of raw empty DF
        to reduce downstream/load failures
    """
    start_date = _parse_date_env("BRUIN_START_DATE", DEFAULT_START)
    end_date = _parse_date_env("BRUIN_END_DATE", DEFAULT_END)

    if end_date < start_date:
        raise ValueError(f"BRUIN_END_DATE {end_date:%Y-%m-%d} is before BRUIN_START_DATE {start_date:%Y-%m-%d}")

    taxi_types = _get_taxi_types()
    months_to_process = _month_starts_between(start_date, end_date)

    extracted_at = datetime.now(timezone.utc).replace(tzinfo=None)  # naive timestamp in UTC
    this_month_utc = _first_day_of_month_utc(datetime.now(timezone.utc))

    all_dataframes: list[pd.DataFrame] = []
    total_downloaded_rows = 0

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

            df = _download_parquet_to_df(url, filename)
            if df is None:
                continue

            df["taxi_type"] = taxi_type
            df["extracted_at"] = extracted_at
            all_dataframes.append(df)

            total_downloaded_rows += len(df)
            print(f"Downloaded {filename} ({len(df)} rows)")

    if not all_dataframes:
        print("No data downloaded for the requested interval. Returning empty DataFrame with schema.")
        return _empty_result()

    combined_df = pd.concat(all_dataframes, ignore_index=True)
    print(f"Total rows combined: {len(combined_df)} (downloaded rows: {total_downloaded_rows})")

    _strip_timezones_inplace(combined_df)
    return combined_df