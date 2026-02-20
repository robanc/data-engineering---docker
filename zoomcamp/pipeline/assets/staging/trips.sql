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
    checks:
      - name: not_null
  - name: dropoff_location_id
    type: integer
    description: "Dropoff location ID"
    checks:
      - name: not_null
  - name: fare_amount
    type: float
    description: "Base fare amount in USD"
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
    checks:
      - name: not_null

custom_checks:
  - name: no_duplicate_trips
    description: "Ensure no duplicate trips exist based on composite key"
    query: |
      SELECT
        COUNT(*) - COUNT(DISTINCT CONCAT(
          CAST(pickup_datetime AS STRING), '|',
          CAST(dropoff_datetime AS STRING), '|',
          CAST(pickup_location_id AS STRING), '|',
          CAST(dropoff_location_id AS STRING)
        ))
      FROM staging.trips
      WHERE pickup_datetime >= TIMESTAMP('{{ start_datetime }}')
        AND pickup_datetime <  TIMESTAMP('{{ end_datetime }}')
    value: 0
@bruin */

WITH normalized_trips AS (
  SELECT
    COALESCE(t.tpep_pickup_datetime,  t.lpep_pickup_datetime)  AS pickup_datetime,
    COALESCE(t.tpep_dropoff_datetime, t.lpep_dropoff_datetime) AS dropoff_datetime,
    t.pu_location_id AS pickup_location_id,
    t.do_location_id AS dropoff_location_id,
    t.fare_amount,
    t.taxi_type,
    t.payment_type
  FROM ingestion.trips t
  WHERE COALESCE(t.tpep_pickup_datetime, t.lpep_pickup_datetime) >= TIMESTAMP('{{ start_datetime }}')
    AND COALESCE(t.tpep_pickup_datetime, t.lpep_pickup_datetime) <  TIMESTAMP('{{ end_datetime }}')
    AND COALESCE(t.tpep_pickup_datetime,  t.lpep_pickup_datetime)  IS NOT NULL
    AND COALESCE(t.tpep_dropoff_datetime, t.lpep_dropoff_datetime) IS NOT NULL
    AND t.pu_location_id IS NOT NULL
    AND t.do_location_id IS NOT NULL
    AND t.fare_amount >= 0
),

joined AS (
  SELECT
    t.pickup_datetime,
    t.dropoff_datetime,
    t.pickup_location_id,
    t.dropoff_location_id,
    t.fare_amount,
    t.taxi_type,
    p.payment_type_name,
    ROW_NUMBER() OVER (
      PARTITION BY
        t.pickup_datetime,
        t.dropoff_datetime,
        t.pickup_location_id,
        t.dropoff_location_id
      ORDER BY t.pickup_datetime
    ) AS rn
  FROM normalized_trips t
  LEFT JOIN ingestion.payment_lookup p
    ON t.payment_type = p.payment_type_id
)

SELECT
  pickup_datetime,
  dropoff_datetime,
  pickup_location_id,
  dropoff_location_id,
  fare_amount,
  taxi_type,
  payment_type_name
FROM joined
WHERE rn = 1
  AND payment_type_name IS NOT NULL;