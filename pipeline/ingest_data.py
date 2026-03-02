import pandas as pd
import pyarrow.parquet as pq
import requests
import os
from sqlalchemy import create_engine
import click

def download_file(url: str, local_path: str):
    """Download a file from a URL if it does not exist locally."""
    if not os.path.exists(local_path):
        print(f"Downloading {url} to {local_path}...")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        print(f"Using existing file {local_path}")

def ingest_csv(file_url: str, table_name: str, engine, chunksize: int = 100_000):
    df_iter = pd.read_csv(file_url, chunksize=chunksize)
    for i, chunk in enumerate(df_iter):
        chunk.to_sql(name=table_name, con=engine, if_exists="append", index=False)
        print(f"Inserted chunk {i+1} into {table_name}")

def ingest_parquet(file_url: str, table_name: str, engine, chunksize: int = 100_000):
    local_file = f"/tmp/{os.path.basename(file_url)}"
    download_file(file_url, local_file)
    
    table = pq.ParquetFile(local_file)
    for i, batch in enumerate(table.iter_batches(batch_size=chunksize)):
        df = batch.to_pandas()
        df.to_sql(name=table_name, con=engine, if_exists="append", index=False)
        print(f"Inserted batch {i+1} into {table_name}")

@click.command()
@click.option("--pg_user", required=True)
@click.option("--pg_pass", required=True)
@click.option("--pg_host", required=True)
@click.option("--pg_port", required=True, type=int)
@click.option("--pg_db", required=True)
@click.option("--target_table", required=True)
@click.option("--year", required=False, type=int)
@click.option("--month", required=False, type=int)
@click.option("--url", required=False)
@click.option("--taxi_type", required=False, type=click.Choice(["yellow", "green"], case_sensitive=False), default="green")
def run(pg_user, pg_pass, pg_host, pg_port, pg_db, target_table, year, month, url, taxi_type):
    engine = create_engine(
        f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    )

    if url:  # Taxi zones or custom CSV
        ingest_csv(url, target_table, engine)
    else:
        if not (year and month):
            raise ValueError("Must provide --year and --month for taxi trip data")
        
        taxi_type = taxi_type.lower()
        parquet_url = f"https://d37ci6vzurychx.cloudfront.net/trip-data/{taxi_type}_tripdata_{year}-{month:02d}.parquet"
        ingest_parquet(parquet_url, target_table, engine)

if __name__ == "__main__":
    run()