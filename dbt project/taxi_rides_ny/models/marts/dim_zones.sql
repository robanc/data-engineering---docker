{{ config(materialized='table') }}

with taxi_zone_lookup as (
    select
      cast(locationid as bigint) as location_id,
      borough,
      zone,
      service_zone
    from {{ ref('taxi_zone_lookup') }}
)

select *
from taxi_zone_lookup
order by location_id