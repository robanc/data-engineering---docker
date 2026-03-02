{{ config(materialized='table') }}

with trips as (
    select
        vendor_id,
        pickup_datetime,
        dropoff_datetime,
        pickup_location_id,
        dropoff_location_id,
        passenger_count,
        trip_distance,
        trip_type,
        fare_amount,
        extra,
        mta_tax,
        tip_amount,
        tolls_amount,
        ehail_fee,
        improvement_surcharge,
        congestion_surcharge,
        total_amount,
        payment_type
    from {{ ref('int_trips_unioned') }}
),

enriched as (
    select
        *,
        case
            when payment_type = 1 then 'Credit card'
            when payment_type = 2 then 'Cash'
            when payment_type = 3 then 'No charge'
            when payment_type = 4 then 'Dispute'
            when payment_type = 5 then 'Unknown'
            when payment_type = 6 then 'Voided trip'
            else 'Unknown'
        end as payment_type_name
    from trips
),

-- exact dedupe (low memory)
deduped as (
    select
        vendor_id,
        pickup_datetime,
        dropoff_datetime,
        pickup_location_id,
        dropoff_location_id,
        passenger_count,
        trip_distance,
        trip_type,
        fare_amount,
        extra,
        mta_tax,
        tip_amount,
        tolls_amount,
        ehail_fee,
        improvement_surcharge,
        congestion_surcharge,
        total_amount,
        payment_type,
        payment_type_name
    from enriched
    group by
        vendor_id,
        pickup_datetime,
        dropoff_datetime,
        pickup_location_id,
        dropoff_location_id,
        passenger_count,
        trip_distance,
        trip_type,
        fare_amount,
        extra,
        mta_tax,
        tip_amount,
        tolls_amount,
        ehail_fee,
        improvement_surcharge,
        congestion_surcharge,
        total_amount,
        payment_type,
        payment_type_name
),

final as (
    select
        md5(
            concat(
                coalesce(cast(vendor_id as varchar), ''),
                '|', coalesce(cast(pickup_datetime as varchar), ''),
                '|', coalesce(cast(dropoff_datetime as varchar), ''),
                '|', coalesce(cast(pickup_location_id as varchar), ''),
                '|', coalesce(cast(dropoff_location_id as varchar), ''),
                '|', coalesce(cast(passenger_count as varchar), ''),
                '|', coalesce(cast(trip_distance as varchar), ''),
                '|', coalesce(cast(total_amount as varchar), ''),
                '|', coalesce(cast(payment_type as varchar), '')
            )
        ) as trip_id,
        *
    from deduped
)

select *
from final