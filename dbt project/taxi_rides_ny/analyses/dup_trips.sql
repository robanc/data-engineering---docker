select
    vendor_id,
    pickup_datetime,
    dropoff_datetime,
    pickup_location_id,
    dropoff_location_id,
    passenger_count,
    trip_distance,
    total_amount,
    payment_type,
    count(*) as cnt
from {{ ref('int_trips_unioned') }}
where pickup_datetime >= '2020-01-01'
  and pickup_datetime <  '2021-01-01'
group by 1,2,3,4,5,6,7,8,9
having count(*) > 1
order by cnt desc
limit 50