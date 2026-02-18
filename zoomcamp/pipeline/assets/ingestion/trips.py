"""@bruin
name: ingestion.trips
type: python
image: python:3.11
connection: bigquery-defaultss

materialization:
  type: table
  strategy: append

# Define key columns for metadata and quality checks.
# Raw data columns will be preserved as-is from parquet files.
columns:
  - name: taxi_type
    type: string
    description: "Taxi type (yellow or green)"
  - name: extracted_at
    type: timestamp
    description: "Timestamp when data was extracted"

@bruin"""

import os
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import requests
from io import BytesIO

def materialize() -> pd.DataFrame:
    """
    Fetch NYC taxi trip data from TLC public endpoint.
    
    Uses taxi_types variable and date range from BRUIN_START_DATE/BRUIN_END_DATE
    to download parquet files and combine them into a single DataFrame.
    Keeps data in its rawest format without any cleaning or transformations.
    """
    # Base URL for TLC trip data
    base_url = "https://d37ci6vzurychx.cloudfront.net/trip-data/"
    
    # Get date range from environment variables
    start_date_str = os.environ.get("BRUIN_START_DATE", "2022-01-01")
    end_date_str = os.environ.get("BRUIN_END_DATE", "2022-01-31")
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    # Get taxi_types variable from environment (default to ["yellow"])
    vars_json = json.loads(os.environ.get("BRUIN_VARS", "{}"))
    taxi_types = vars_json.get("taxi_types", ["yellow"])
    
    # Generate list of months to process
    months_to_process = []
    current_date = start_date.replace(day=1)  # Start from first day of month
    
    while current_date <= end_date:
        months_to_process.append(current_date)
        current_date += relativedelta(months=1)
    
    # Download and combine parquet files
    all_dataframes = []
    extracted_at = datetime.now()
    
    for month_date in months_to_process:
        year = month_date.year
        month = month_date.month
        
        for taxi_type in taxi_types:
            # Construct filename: <taxi_type>_tripdata_<year>-<month>.parquet
            filename = f"{taxi_type}_tripdata_{year}-{month:02d}.parquet"
            url = f"{base_url}{filename}"
            
            try:
                # Download parquet file
                response = requests.get(url, timeout=60)
                response.raise_for_status()
                
                # Read parquet into DataFrame
                df = pd.read_parquet(BytesIO(response.content))
                
                # Add taxi_type column to identify the source
                df['taxi_type'] = taxi_type
                
                # Add extracted_at timestamp for lineage/debugging
                df['extracted_at'] = extracted_at
                
                all_dataframes.append(df)
                print(f"Downloaded and loaded {filename} ({len(df)} rows)")
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    print(f"File not found: {filename} (skipping)")
                else:
                    raise
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                raise
    
    # Combine all DataFrames
    if not all_dataframes:
        print("Warning: No data downloaded. Returning empty DataFrame.")
        return pd.DataFrame()
    
    combined_df = pd.concat(all_dataframes, ignore_index=True)
    print(f"Total rows combined: {len(combined_df)}")

    # Fix pyarrow/dlt timezone issue on Windows: make datetimes timezone-naive
    for col in combined_df.columns:
        if pd.api.types.is_datetime64_any_dtype(combined_df[col]):
            try:
                combined_df[col] = pd.to_datetime(combined_df[col], errors="coerce").dt.tz_localize(None)
            except Exception:
                pass

    # Also handle object columns that may contain datetimes
    for col in combined_df.select_dtypes(include=["object"]).columns:
        if col.endswith("datetime") or "datetime" in col.lower():
            try:
                parsed = pd.to_datetime(combined_df[col], errors="coerce")
                # if it parsed into datetimes, strip tz
                if pd.api.types.is_datetime64_any_dtype(parsed):
                    combined_df[col] = parsed.dt.tz_localize(None)
            except Exception:
                pass

    return combined_df


