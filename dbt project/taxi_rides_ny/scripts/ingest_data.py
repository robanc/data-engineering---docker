import duckdb
import requests
from pathlib import Path

BASE_URL = "https://github.com/DataTalksClub/nyc-tlc-data/releases/download"

def download_and_convert_files(taxi_type):
    data_dir = Path("data") / taxi_type
    data_dir.mkdir(exist_ok=True, parents=True)

    for year in [2019, 2020]:
        for month in range(1, 13):
            parquet_filename = f"{taxi_type}_tripdata_{year}-{month:02d}.parquet"
            parquet_filepath = data_dir / parquet_filename

            if parquet_filepath.exists():
                print(f"Skipping {parquet_filename}")
                continue

            csv_gz_filename = f"{taxi_type}_tripdata_{year}-{month:02d}.csv.gz"
            csv_gz_filepath = data_dir / csv_gz_filename

            response = requests.get(f"{BASE_URL}/{taxi_type}/{csv_gz_filename}", stream=True)
            response.raise_for_status()

            with open(csv_gz_filepath, 'wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)

            con = duckdb.connect()
            con.execute(f"""
                COPY (SELECT * FROM read_csv_auto('{csv_gz_filepath}'))
                TO '{parquet_filepath}' (FORMAT PARQUET)
            """)
            con.close()

            csv_gz_filepath.unlink()
            print(f"Completed {parquet_filename}")

if __name__ == "__main__":
    for t in ["yellow", "green"]:
        download_and_convert_files(t)

    con = duckdb.connect("taxi_rides_ny.duckdb")
    con.execute("CREATE SCHEMA IF NOT EXISTS prod")

    for t in ["yellow", "green"]:
        con.execute(f"""
            CREATE OR REPLACE TABLE prod.{t}_tripdata AS
            SELECT * FROM read_parquet('data/{t}/*.parquet', union_by_name=true)
        """)

    con.close()