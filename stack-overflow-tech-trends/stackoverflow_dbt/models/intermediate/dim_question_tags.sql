{{ config(materialized='table') }}

select
    id as question_id,
    tag
from {{ source('stackoverflow_raw', 'stg_questions_ext') }},
unnest(split(tags, '|')) as tag
where tag is not null
