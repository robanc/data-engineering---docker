/* @bruin
name: staging.trips
type: bq.sql
connection: bigquery-default

depends:
  - ingestion.trips
  - ingestion.payment_lookup

materialization:
  type: table
  strategy: time_interval
  incremental_key: pickup_datetime
  time_granularity: timestamp

columns:
  - name: pickup_datetime
    type: timestamp
    description: "Trip pickup timestamp"
    primary_key: true
    checks:
      - name: not_null
  - name: dropoff_datetime
    type: timestamp
    description: "Trip dropoff timestamp"
    checks:
      - name: not_null
  - name: pickup_location_id
    type: integer
    description: "Pickup location ID"
    primary_key: true
  - name: dropoff_location_id
    type: integer
    description: "Dropoff location ID"
    primary_key: true
  - name: fare_amount
    type: float
    description: "Base fare amount in USD"
    primary_key: true
    checks:
      - name: non_negative
  - name: taxi_type
    type: string
    description: "Taxi type (yellow or green)"
    checks:
      - name: not_null
  - name: payment_type_name
    type: string
    description: "Human-readable payment type"

custom_checks:
  - name: no_duplicate_trips
    description: "Ensure no duplicate trips exist based on composite key"
    query: |
      SELECT
        COUNT(*) - COUNT(DISTINCT CONCAT(
          CAST(pickup_datetime AS STRING), '|',
          COALESCE(CAST(pickup_location_id AS STRING), ''), '|',
          COALESCE(CAST(dropoff_location_id AS STRING), ''), '|',
        ))
      FROM staging.trips
    value: 0

@bruin */

WITH normalized_trips AS (
  SELECT
    -- Normalize datetime columns (yellow uses tpep_*, green uses lpep_*)
    COALESCE(t.tpep_pickup_datetime, t.lpep_pickup_datetime)   AS pickup_datetime,
    COALESCE(t.tpep_dropoff_datetime, t.lpep_dropoff_datetime) AS dropoff_datetime,

    -- Location columns (these are the actual columns in ingestion.trips in BigQuery)
    t.pu_location_id AS pickup_location_id,
    t.do_location_id AS dropoff_location_id,

    -- Fare amount
    t.fare_amount,

    -- Taxi type
    t.taxi_type,

    -- Payment type for joining
    t.payment_type
  FROM ingestion.trips t
  WHERE COALESCE(t.tpep_pickup_datetime, t.lpep_pickup_datetime) >= '{{ start_datetime }}'
    AND COALESCE(t.tpep_pickup_datetime, t.lpep_pickup_datetime) <  '{{ end_datetime }}'
    -- Filter out invalid rows
    AND COALESCE(t.tpep_pickup_datetime, t.lpep_pickup_datetime)   IS NOT NULL
    AND COALESCE(t.tpep_dropoff_datetime, t.lpep_dropoff_datetime) IS NOT NULL
    AND t.fare_amount >= 0
)

SELECT
  pickup_datetime,
  dropoff_datetime,
  pickup_location_id,
  dropoff_location_id,
  fare_amount,
  taxi_type,
  p.payment_type_name
FROM normalized_trips t
LEFT JOIN ingestion.payment_lookup p
  ON t.payment_type = p.payment_type_id
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY
    pickup_datetime,
    dropoff_datetime,
    pickup_location_id,
    dropoff_location_id
  ORDER BY pickup_datetime
) = 1;