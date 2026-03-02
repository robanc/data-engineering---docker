{{ config(materialized='table') }}

with green_trips as (
    select * from {{ ref('stg_green_tripdata') }}
),
yellow_trips as (
    select * from {{ ref('stg_yellow_tripdata') }}
)
select * from green_trips
union all
select * from yellow_trips