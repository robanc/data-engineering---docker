with trips_union as (
    select * from {{ ref('int_trips_unioned') }}
),

vendors as (
    select distinct
        vendor_id,
        {{ get_vendor_names('vendor_id') }} as vendor_name
    from trips_union
    where vendor_id is not null
)

select *
from vendors
order by vendor_id