/* @bruin
name: reports.trips_report
type: bigquery.sql
connection: bigquery-defaultss

depends:
  - staging.trips

materialization:
  type: table
  strategy: time_interval
  incremental_key: trip_date
  time_granularity: date

columns:
  - name: trip_date
    type: date
    description: "Date of the trip"
    primary_key: true
    checks:
      - name: not_null
  - name: taxi_type
    type: string
    description: "Taxi type (yellow or green)"
    primary_key: true
    checks:
      - name: not_null
  - name: payment_type
    type: string
    description: "Payment type name"
    primary_key: true
    checks:
      - name: not_null
  - name: trip_count
    type: bigint
    description: "Number of trips"
    checks:
      - name: non_negative
      - name: positive
  - name: total_fare
    type: float
    description: "Total fare amount in USD"
    checks:
      - name: non_negative
  - name: avg_fare
    type: float
    description: "Average fare amount in USD"
    checks:
      - name: non_negative

custom_checks:
  - name: has_report_data
    description: "Ensure report contains data"
    query: |
      SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
      FROM reports.trips_report
    value: 1

@bruin */

SELECT
    DATE(pickup_datetime) AS trip_date,
    taxi_type,
    payment_type_name AS payment_type,
    COUNT(*) AS trip_count,
    SUM(fare_amount) AS total_fare,
    AVG(fare_amount) AS avg_fare
FROM staging.trips
WHERE pickup_datetime >= '{{ start_datetime }}'
  AND pickup_datetime < '{{ end_datetime }}'
GROUP BY 1, 2, 3
