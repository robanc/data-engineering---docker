"""@bruin
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
@bruin"""

import json
import os
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta


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
    # normalize
    if isinstance(taxi_types, str):
        taxi_types = [taxi_types]
    return [str(t).strip() for t in taxi_types if str(t).strip()]


def _month_starts_between(start_date: datetime, end_date: datetime) -> list[datetime]:
    """
    Generate a list of month-start datetimes (naive) from start_date to end_date (inclusive).
    """
    months: list[datetime] = []
    current = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

    while current <= end:
        months.append(current)
        current = current + relativedelta(months=1)
    return months


def _strip_timezones_inplace(df: pd.DataFrame) -> None:
    """
    Make all datetime-like columns timezone-naive.
    This helps avoid pyarrow timezone issues when writing.
    """
    # datetime64 columns
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.tz_localize(None)
            except Exception:
                pass

    # object columns that likely contain datetimes
    for col in df.select_dtypes(include=["object"]).columns:
        col_l = col.lower()
        if col.endswith("datetime") or "datetime" in col_l or col.endswith("_at") or col_l.endswith("_ts"):
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if pd.api.types.is_datetime64_any_dtype(parsed):
                    df[col] = parsed.dt.tz_localize(None)
            except Exception:
                pass


def materialize() -> pd.DataFrame:
    """
    Fetch NYC taxi trip data from TLC public endpoint.

    Uses taxi_types variable and date range from BRUIN_START_DATE / BRUIN_END_DATE
    to download parquet files and combine them into a single DataFrame.

    Skips:
      - current/future months (to avoid attempting unpublished data)
      - missing/unavailable months (HTTP 403/404)

    Returns:
      A combined DataFrame with raw columns + taxi_type + extracted_at.
      If no files are available, returns an empty DataFrame.
    """
    base_url = "https://d37ci6vzurychx.cloudfront.net/trip-data/"

    # dates from Bruin interval
    start_date = _parse_date_env("BRUIN_START_DATE", "2022-01-01")
    end_date = _parse_date_env("BRUIN_END_DATE", "2022-01-31")

    taxi_types = _get_taxi_types()

    months_to_process = _month_starts_between(start_date, end_date)
    extracted_at = datetime.now(timezone.utc).replace(tzinfo=None)  # store as naive timestamp

    # Don't attempt current/future month
    this_month_utc = _first_day_of_month_utc(datetime.now(timezone.utc))

    all_dataframes: list[pd.DataFrame] = []

    for month_date in months_to_process:
        month_start_utc = _first_day_of_month_utc(month_date.replace(tzinfo=timezone.utc))
        if month_start_utc >= this_month_utc:
            print(f"Skipping {month_date:%Y-%m} (current/future month)")
            continue

        year = month_date.year
        month = month_date.month

        for taxi_type in taxi_types:
            filename = f"{taxi_type}_tripdata_{year}-{month:02d}.parquet"
            url = f"{base_url}{filename}"

            try:
                response = requests.get(url, timeout=60)
                response.raise_for_status()

                df = pd.read_parquet(BytesIO(response.content))

                df["taxi_type"] = taxi_type
                df["extracted_at"] = extracted_at

                all_dataframes.append(df)
                print(f"Downloaded and loaded {filename} ({len(df)} rows)")

            except requests.exceptions.HTTPError as e:
                status = getattr(e.response, "status_code", None)
                # TLC may return 404 (not found) or 403 (forbidden) for unavailable files
                if status in (403, 404):
                    print(f"Unavailable ({status}) for {filename} (skipping)")
                    continue
                print(f"HTTP error for {filename}: {e}")
                raise
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                raise

    if not all_dataframes:
        print("Warning: No data downloaded. Returning empty DataFrame.")
        return pd.DataFrame()

    combined_df = pd.concat(all_dataframes, ignore_index=True)
    print(f"Total rows combined: {len(combined_df)}")

    _strip_timezones_inplace(combined_df)
    return combined_df