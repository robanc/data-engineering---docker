import dlt
import requests
from typing import Iterator, Dict, Any

BASE_URL = "https://us-central1-dlthub-analytics.cloudfunctions.net/data_engineering_zoomcamp_api"

@dlt.resource(name="trips", write_disposition="append")
def trips(taxi: str, year: int, month: int, page_size: int = 1000) -> Iterator[Dict[str, Any]]:
    page = 1

    while True:
        response = requests.get(
            BASE_URL,
            params={
                "taxi": taxi,
                "year": year,
                "month": month,
                "page": page,
                "page_size": page_size
            },
            timeout=60
        )
        response.raise_for_status()
        data = response.json()

        # Stop when empty page returned (Zoomcamp requirement)
        if not data:
            break

        for row in data:
            yield row

        page += 1


@dlt.source(name="nyc_taxi_api")
def nyc_taxi_source(taxi="yellow", year=2020, month=1):
    yield trips(taxi=taxi, year=year, month=month)


if __name__ == "__main__":
    pipeline = dlt.pipeline(
        pipeline_name="taxi_pipeline",
        destination="duckdb",
        dataset_name="nyc_taxi"
    )

    info = pipeline.run(
        nyc_taxi_source(taxi="yellow", year=2020, month=1),
        table_name="yellow_tripdata"
    )

    print(info)