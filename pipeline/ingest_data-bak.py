#!/usr/bin/env python
# coding: utf-8

import click
import pandas as pd
from sqlalchemy import create_engine
from tqdm.auto import tqdm


dtype = {
    "VendorID": "Int64",
    "passenger_count": "Int64",
    "trip_distance": "float64",
    "RatecodeID": "Int64",
    "store_and_fwd_flag": "string",
    "PULocationID": "Int64",
    "DOLocationID": "Int64",
    "payment_type": "Int64",
    "fare_amount": "float64",
    "extra": "float64",
    "mta_tax": "float64",
    "tip_amount": "float64",
    "tolls_amount": "float64",
    "improvement_surcharge": "float64",
    "total_amount": "float64",
    "congestion_surcharge": "float64"
}

parse_dates = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime"
]


@click.command()
@click.option('--pg_user', default='root')
@click.option('--pg_pass', default='root')
@click.option('--pg_host', default='localhost')
@click.option('--pg_port', default=5432, type=int)
@click.option('--pg_db', default='ny_taxi')
@click.option('--year', type=int, required=False)
@click.option('--month', type=int, required=False)
@click.option('--chunksize', default=100000, type=int)
@click.option('--target_table', required=True)
@click.option('--url', required=False, help='Full CSV URL (for lookup tables, etc.)')
def run(pg_user, pg_pass, pg_host, pg_port, pg_db, year, month, chunksize, target_table, url):

    # --------------------
    # Decide data source
    # --------------------
    if url:
        csv_url = url
        print(f"Using provided URL: {csv_url}")
        df_iter = pd.read_csv(csv_url, iterator=True, chunksize=1000)

    else:
        if year is None or month is None:
            raise ValueError("If --url is not provided, --year and --month must be set")

        prefix = "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/yellow"
        csv_url = f"{prefix}/yellow_tripdata_{year}-{month:02d}.csv.gz"
        print(f"Using generated URL: {csv_url}")

        df_iter = pd.read_csv(
            csv_url,
            dtype=dtype,
            parse_dates=parse_dates,
            iterator=True,
            chunksize=chunksize
        )

    # --------------------
    # Postgres connection
    # --------------------
    engine = create_engine(
        f'postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}'
    )

    # --------------------
    # Ingestion loop
    # --------------------
    first = True

    for df_chunk in tqdm(df_iter):

        if first:
            df_chunk.head(0).to_sql(
                name=target_table,
                con=engine,
                if_exists="replace"
            )
            first = False
            print(f"Table {target_table} created")

        df_chunk.to_sql(
            name=target_table,
            con=engine,
            if_exists="append"
        )

        print("Inserted:", len(df_chunk))

    print("✅ Ingestion finished")


if __name__ == "__main__":
    run()
