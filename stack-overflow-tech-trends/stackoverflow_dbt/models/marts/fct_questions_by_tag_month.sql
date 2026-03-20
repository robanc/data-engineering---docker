{{
  config(
    materialized='table',
    partition_by={
      "field": "month",
      "data_type": "date"
    },
    cluster_by=["tag"]
  )
}}

select
    date_trunc(date(q.creation_date), month) as month,
    t.tag,
    count(*) as question_count,
    avg(q.score) as avg_score,
    avg(q.view_count) as avg_views
from {{ source('stackoverflow_raw', 'stg_questions_ext') }} q
join {{ ref('dim_question_tags') }} t
  on q.id = t.question_id
group by 1, 2
