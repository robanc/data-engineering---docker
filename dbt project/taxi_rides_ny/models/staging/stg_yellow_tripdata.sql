select
    -- identifiers
    cast(VendorID as bigint)      as vendor_id,
    cast(RatecodeID as bigint)    as rate_code_id,
    cast(PULocationID as bigint)  as pickup_location_id,
    cast(DOLocationID as bigint)  as dropoff_location_id,

    -- timestamps (YELLOW uses tpep_*)
    cast(tpep_pickup_datetime as timestamp)  as pickup_datetime,
    cast(tpep_dropoff_datetime as timestamp) as dropoff_datetime,

    -- trip info
    store_and_fwd_flag,
    cast(passenger_count as bigint) as passenger_count,
    cast(trip_distance as double)   as trip_distance,
    cast(1 as bigint)               as trip_type,  -- yellow taxis only

    -- payment info
    cast(fare_amount as decimal(18,2))           as fare_amount,
    cast(extra as decimal(18,2))                 as extra,
    cast(mta_tax as decimal(18,2))               as mta_tax,
    cast(tip_amount as decimal(18,2))            as tip_amount,
    cast(tolls_amount as decimal(18,2))          as tolls_amount,
    cast(0 as decimal(18,2))                     as ehail_fee, -- yellow: none
    cast(improvement_surcharge as decimal(18,2)) as improvement_surcharge,
    cast(total_amount as decimal(18,2))          as total_amount,
    cast(payment_type as bigint)                 as payment_type,
    cast(congestion_surcharge as decimal(18,2))  as congestion_surcharge

from {{ source('raw_data', 'yellow_tripdata') }}