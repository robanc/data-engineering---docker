{{ config(materialized='table') }}

select
    tag,
    sum(question_count) as total_questions,
    avg(avg_score) as avg_score
from {{ ref('fct_questions_by_tag_month') }}
group by 1
qualify row_number() over (order by total_questions desc) <= 50
