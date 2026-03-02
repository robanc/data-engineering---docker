/* @bruin
name: reports.trips_report
type: bq.sql
connection: bigquery-default

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
    description: "Report has at least 1 row for the interval"
    query: |
      SELECT IF(COUNT(*) > 0, 1, 0) AS ok
      FROM reports.trips_report
      WHERE trip_date BETWEEN DATE(TIMESTAMP('{{ start_datetime }}'))
                          AND DATE(TIMESTAMP('{{ end_datetime }}'))
    operator: "="
    value: 1

@bruin */

SELECT
  DATE(pickup_datetime) AS trip_date,
  taxi_type,
  COALESCE(payment_type_name, 'Unknown') AS payment_type,
  COUNT(*) AS trip_count,
  SUM(fare_amount) AS total_fare,
  AVG(fare_amount) AS avg_fare
FROM staging.trips
WHERE pickup_datetime >= TIMESTAMP('{{ start_datetime }}')
  AND pickup_datetime <  TIMESTAMP('{{ end_datetime }}')
GROUP BY 1, 2, 3